"""
creation.py
--------------

Create meshes from primitives, or with operations.
"""

from .base import Trimesh
from .constants import log, tol
from .geometry import faces_to_edges, align_vectors, plane_transform

from . import util
from . import grouping
from . import triangles
from . import transformations as tf

import numpy as np
import collections

try:
    # shapely is a soft dependency
    from shapely.geometry import Polygon
    from shapely.wkb import loads as load_wkb
except BaseException as E:
    # shapely will sometimes raise OSErrors
    # on import rather than just ImportError
    from . import exceptions
    # re-raise the exception when someone tries
    # to use the module that they don't have
    Polygon = exceptions.closure(E)
    load_wkb = exceptions.closure(E)


def revolve(linestring,
            angle=None,
            sections=None,
            transform=None,
            **kwargs):
    """
    Revolve a 2D line string around the 2D Y axis, with a result with
    the 2D Y axis pointing along the 3D Z axis.

    This function is intended to handle the complexity of indexing
    and is intended to be used to create all radially symmetric primitives,
    eventually including cylinders, annular cylinders, capsules, cones,
    and UV spheres.

    Note that if your linestring is closed, it needs to be counterclockwise
    if you would like face winding and normals facing outwards.

    Parameters
    -------------
    linestring : (n, 2) float
      Lines in 2D which will be revolved
    angle : None or float
      Angle in radians to revolve curve by
    sections : None or int
      Number of sections result should have
      If not specified default is 32 per revolution
    transform : None or (4, 4) float
      Transform to apply to mesh after construction
    **kwargs : dict
      Passed to Trimesh constructor

    Returns
    --------------
    revolved : Trimesh
      Mesh representing revolved result
    """
    linestring = np.asanyarray(linestring, dtype=np.float64)

    # linestring must be ordered 2D points
    if len(linestring.shape) != 2 or linestring.shape[1] != 2:
        raise ValueError('linestring must be 2D!')

    if angle is None:
        # default to closing the revolution
        angle = np.pi * 2
        closed = True
    else:
        # check passed angle value
        closed = angle >= ((np.pi * 2) - 1e-8)

    if sections is None:
        # default to 32 sections for a full revolution
        sections = int(angle / (np.pi * 2) * 32)
    # change to face count
    sections += 1
    # create equally spaced angles
    theta = np.linspace(0, angle, sections)

    # 2D points around the revolution
    points = np.column_stack((np.cos(theta), np.sin(theta)))

    # how many points per slice
    per = len(linestring)
    # use the 2D X component as radius
    radius = linestring[:, 0]
    # use the 2D Y component as the height along revolution
    height = linestring[:, 1]
    # a lot of tiling to get our 3D vertices
    vertices = np.column_stack((
        np.tile(points, (1, per)).reshape((-1, 2)) *
        np.tile(radius, len(points)).reshape((-1, 1)),
        np.tile(height, len(points))))

    if closed:
        # should be a duplicate set of vertices
        assert np.allclose(vertices[:per],
                           vertices[-per:])
        # chop off duplicate vertices
        vertices = vertices[:-per]

    if transform is not None:
        # apply transform to vertices
        vertices = tf.transform_points(vertices, transform)

    # how many slices of the pie
    slices = len(theta) - 1

    # start with a quad for every segment
    # this is a superset which will then be reduced
    quad = np.array([0, per, 1,
                     1, per, per + 1])
    # stack the faces for a single slice of the revolution
    single = np.tile(quad, per).reshape((-1, 3))
    # `per` is basically the stride of the vertices
    single += np.tile(np.arange(per), (2, 1)).T.reshape((-1, 1))
    # remove any zero-area triangle
    # this covers many cases without having to think too much
    single = single[triangles.area(vertices[single]) > tol.merge]

    # how much to offset each slice
    # note arange multiplied by vertex stride
    # but tiled by the number of faces we actually have
    offset = np.tile(np.arange(slices) * per,
                     (len(single), 1)).T.reshape((-1, 1))
    # stack a single slice into N slices
    stacked = np.tile(single.ravel(), slices).reshape((-1, 3))

    if tol.strict:
        # make sure we didn't screw up stacking operation
        assert np.allclose(stacked.reshape((-1, single.shape[0], 3)) - single, 0)

    # offset stacked and wrap vertices
    faces = (stacked + offset) % len(vertices)

    # create the mesh from our vertices and faces
    mesh = Trimesh(vertices=vertices, faces=faces)

    # strict checks run only in unit tests
    if (tol.strict and
        np.allclose(radius[[0, -1]], 0.0) or
            np.allclose(linestring[0], linestring[-1])):
        # if revolved curve starts and ends with zero radius
        # it should really be a valid volume, unless the sign
        # reversed on the input linestring
        assert mesh.is_volume

    return mesh


def extrude_polygon(polygon,
                    height,
                    transform=None,
                    triangle_args=None,
                    **kwargs):
    """
    Extrude a 2D shapely polygon into a 3D mesh

    Parameters
    ----------
    polygon : shapely.geometry.Polygon
      2D geometry to extrude
    height : float
      Distance to extrude polygon along Z
    triangle_args : str or None
      Passed to triangle
    **kwargs:
        passed to Trimesh

    Returns
    ----------
    mesh : trimesh.Trimesh
      Resulting extrusion as watertight body
    """
    # create a triangulation from the polygon
    vertices, faces = triangulate_polygon(
        polygon, triangle_args=triangle_args, **kwargs)
    # extrude that triangulation along Z
    mesh = extrude_triangulation(vertices=vertices,
                                 faces=faces,
                                 height=height,
                                 transform=transform,
                                 **kwargs)
    return mesh


def sweep_polygon(polygon,
                  path,
                  angles=None,
                  **kwargs):
    """
    Extrude a 2D shapely polygon into a 3D mesh along an
    arbitrary 3D path. Doesn't handle sharp curvature well.


    Parameters
    ----------
    polygon : shapely.geometry.Polygon
      Profile to sweep along path
    path : (n, 3) float
      A path in 3D
    angles :  (n,) float
      Optional rotation angle relative to prior vertex
      at each vertex

    Returns
    -------
    mesh : trimesh.Trimesh
      Geometry of result
    """

    path = np.asanyarray(path, dtype=np.float64)
    if not util.is_shape(path, (-1, 3)):
        raise ValueError('Path must be (n, 3)!')

    # Extract 2D vertices and triangulation
    verts_2d = np.array(polygon.exterior)[:-1]
    base_verts_2d, faces_2d = triangulate_polygon(polygon, **kwargs)
    n = len(verts_2d)

    # Create basis for first planar polygon cap
    x, y, z = util.generate_basis(path[0] - path[1])
    tf_mat = np.ones((4, 4))
    tf_mat[:3, :3] = np.c_[x, y, z]
    tf_mat[:3, 3] = path[0]

    # Compute 3D locations of those vertices
    verts_3d = np.c_[verts_2d, np.zeros(n)]
    verts_3d = tf.transform_points(verts_3d, tf_mat)
    base_verts_3d = np.c_[base_verts_2d,
                          np.zeros(len(base_verts_2d))]
    base_verts_3d = tf.transform_points(base_verts_3d,
                                        tf_mat)

    # keep matching sequence of vertices and 0- indexed faces
    vertices = [base_verts_3d]
    faces = [faces_2d]

    # Compute plane normals for each turn --
    # each turn induces a plane halfway between the two vectors
    v1s = util.unitize(path[1:-1] - path[:-2])
    v2s = util.unitize(path[1:-1] - path[2:])
    norms = np.cross(np.cross(v1s, v2s), v1s + v2s)
    norms[(norms == 0.0).all(1)] = v1s[(norms == 0.0).all(1)]
    norms = util.unitize(norms)
    final_v1 = util.unitize(path[-1] - path[-2])
    norms = np.vstack((norms, final_v1))
    v1s = np.vstack((v1s, final_v1))

    # Create all side walls by projecting the 3d vertices into each plane
    # in succession
    for i in range(len(norms)):
        verts_3d_prev = verts_3d

        # Rotate if needed
        if angles is not None:
            tf_mat = tf.rotation_matrix(angles[i],
                                        norms[i],
                                        path[i])
            verts_3d_prev = tf.transform_points(verts_3d_prev,
                                                tf_mat)

        # Project vertices onto plane in 3D
        ds = np.einsum('ij,j->i', (path[i + 1] - verts_3d_prev), norms[i])
        ds = ds / np.dot(v1s[i], norms[i])

        verts_3d_new = np.einsum('i,j->ij', ds, v1s[i]) + verts_3d_prev

        # Add to face and vertex lists
        new_faces = [[i + n, (i + 1) % n, i] for i in range(n)]
        new_faces.extend([[(i - 1) % n + n, i + n, i] for i in range(n)])

        # save faces and vertices into a sequence
        faces.append(np.array(new_faces))
        vertices.append(np.vstack((verts_3d, verts_3d_new)))

        verts_3d = verts_3d_new

    # do the main stack operation from a sequence to (n,3) arrays
    # doing one vstack provides a substantial speedup by
    # avoiding a bunch of temporary  allocations
    vertices, faces = util.append_faces(vertices, faces)

    # Create final cap
    x, y, z = util.generate_basis(path[-1] - path[-2])
    vecs = verts_3d - path[-1]
    coords = np.c_[np.einsum('ij,j->i', vecs, x),
                   np.einsum('ij,j->i', vecs, y)]
    base_verts_2d, faces_2d = triangulate_polygon(Polygon(coords))
    base_verts_3d = (np.einsum('i,j->ij', base_verts_2d[:, 0], x) +
                     np.einsum('i,j->ij', base_verts_2d[:, 1], y)) + path[-1]
    faces = np.vstack((faces, faces_2d + len(vertices)))
    vertices = np.vstack((vertices, base_verts_3d))

    return Trimesh(vertices, faces)


def extrude_triangulation(vertices,
                          faces,
                          height,
                          transform=None,
                          **kwargs):
    """
    Extrude a 2D triangulation into a watertight mesh.

    Parameters
    ----------
    vertices : (n, 2) float
      2D vertices
    faces : (m, 3) int
      Triangle indexes of vertices
    height : float
      Distance to extrude triangulation
    **kwargs : dict
      Passed to Trimesh constructor

    Returns
    ---------
    mesh : trimesh.Trimesh
      Mesh created from extrusion
    """
    vertices = np.asanyarray(vertices, dtype=np.float64)
    height = float(height)
    faces = np.asanyarray(faces, dtype=np.int64)

    if not util.is_shape(vertices, (-1, 2)):
        raise ValueError('Vertices must be (n,2)')
    if not util.is_shape(faces, (-1, 3)):
        raise ValueError('Faces must be (n,3)')
    if np.abs(height) < tol.merge:
        raise ValueError('Height must be nonzero!')

    # make sure triangulation winding is pointing up
    normal_test = triangles.normals(
        [util.stack_3D(vertices[faces[0]])])[0]

    normal_dot = np.dot(normal_test,
                        [0.0, 0.0, np.sign(height)])[0]

    # make sure the triangulation is aligned with the sign of
    # the height we've been passed
    if normal_dot < 0.0:
        faces = np.fliplr(faces)

    # stack the (n,3) faces into (3*n, 2) edges
    edges = faces_to_edges(faces)
    edges_sorted = np.sort(edges, axis=1)
    # edges which only occur once are on the boundary of the polygon
    # since the triangulation may have subdivided the boundary of the
    # shapely polygon, we need to find it again
    edges_unique = grouping.group_rows(
        edges_sorted, require_count=1)

    # (n, 2, 2) set of line segments (positions, not references)
    boundary = vertices[edges[edges_unique]]

    # we are creating two vertical  triangles for every 2D line segment
    # on the boundary of the 2D triangulation
    vertical = np.tile(boundary.reshape((-1, 2)), 2).reshape((-1, 2))
    vertical = np.column_stack((vertical,
                                np.tile([0, height, 0, height],
                                        len(boundary))))
    vertical_faces = np.tile([3, 1, 2, 2, 1, 0],
                             (len(boundary), 1))
    vertical_faces += np.arange(len(boundary)).reshape((-1, 1)) * 4
    vertical_faces = vertical_faces.reshape((-1, 3))

    # stack the (n,2) vertices with zeros to make them (n, 3)
    vertices_3D = util.stack_3D(vertices)

    # a sequence of zero- indexed faces, which will then be appended
    # with offsets to create the final mesh
    faces_seq = [faces[:, ::-1],
                 faces.copy(),
                 vertical_faces]
    vertices_seq = [vertices_3D,
                    vertices_3D.copy() + [0.0, 0, height],
                    vertical]

    # append sequences into flat nicely indexed arrays
    vertices, faces = util.append_faces(vertices_seq, faces_seq)
    if transform is not None:
        # apply transform here to avoid later bookkeeping
        vertices = tf.transform_points(
            vertices, transform)
        # if the transform flips the winding flip faces back
        # so that the normals will be facing outwards
        if tf.flips_winding(transform):
            # fliplr makes arrays non-contiguous
            faces = np.ascontiguousarray(np.fliplr(faces))
    # create mesh object with passed keywords
    mesh = Trimesh(vertices=vertices,
                   faces=faces,
                   **kwargs)
    # only check in strict mode (unit tests)
    if tol.strict:
        assert mesh.volume > 0.0

    return mesh


def triangulate_polygon(polygon,
                        triangle_args=None,
                        engine=None,
                        **kwargs):
    """
    Given a shapely polygon create a triangulation using a
    python interface to `triangle.c` or mapbox-earcut.
    > pip install triangle
    > pip install mapbox_earcut

    Parameters
    ---------
    polygon : Shapely.geometry.Polygon
        Polygon object to be triangulated
    triangle_args : str or None
        Passed to triangle.triangulate i.e: 'p', 'pq30'
    engine : None or str
      Any value other than 'earcut' will use `triangle`

    Returns
    --------------
    vertices : (n, 2) float
       Points in space
    faces : (n, 3) int
       Index of vertices that make up triangles
    """
    if engine == 'earcut':
        from mapbox_earcut import triangulate_float64

        # get vertices as sequence where exterior is the first value
        vertices = [np.array(polygon.exterior)]
        vertices.extend(np.array(i) for i in polygon.interiors)
        # record the index from the length of each vertex array
        rings = np.cumsum([len(v) for v in vertices])
        # stack vertices into (n, 2) float array
        vertices = np.vstack(vertices)
        # run triangulation
        faces = triangulate_float64(vertices, rings).reshape(
            (-1, 3)).astype(np.int64).reshape((-1, 3))

        return vertices, faces

    # do the import here for soft requirement
    from triangle import triangulate
    # set default triangulation arguments if not specified
    if triangle_args is None:
        triangle_args = 'p'
    # turn the polygon in to vertices, segments, and hole points
    arg = _polygon_to_kwargs(polygon)
    # run the triangulation
    result = triangulate(arg, triangle_args)

    return result['vertices'], result['triangles']


def _polygon_to_kwargs(polygon):
    """
    Given a shapely polygon generate the data to pass to
    the triangle mesh generator

    Parameters
    ---------
    polygon : Shapely.geometry.Polygon
      Input geometry

    Returns
    --------
    result : dict
      Has keys: vertices, segments, holes
    """

    if not polygon.is_valid:
        raise ValueError('invalid shapely polygon passed!')

    def round_trip(start, length):
        """
        Given a start index and length, create a series of (n, 2) edges which
        create a closed traversal.

        Examples
        ---------
        start, length = 0, 3
        returns:  [(0,1), (1,2), (2,0)]
        """
        tiled = np.tile(np.arange(start, start + length).reshape((-1, 1)), 2)
        tiled = tiled.reshape(-1)[1:-1].reshape((-1, 2))
        tiled = np.vstack((tiled, [tiled[-1][-1], tiled[0][0]]))
        return tiled

    def add_boundary(boundary, start):
        # coords is an (n, 2) ordered list of points on the polygon boundary
        # the first and last points are the same, and there are no
        # guarantees on points not being duplicated (which will
        # later cause meshpy/triangle to shit a brick)
        coords = np.array(boundary.coords)
        # find indices points which occur only once, and sort them
        # to maintain order
        unique = np.sort(grouping.unique_rows(coords)[0])
        cleaned = coords[unique]

        vertices.append(cleaned)
        facets.append(round_trip(start, len(cleaned)))

        # holes require points inside the region of the hole, which we find
        # by creating a polygon from the cleaned boundary region, and then
        # using a representative point. You could do things like take the mean of
        # the points, but this is more robust (to things like concavity), if
        # slower.
        test = Polygon(cleaned)
        holes.append(np.array(test.representative_point().coords)[0])

        return len(cleaned)

    # sequence of (n,2) points in space
    vertices = collections.deque()
    # sequence of (n,2) indices of vertices
    facets = collections.deque()
    # list of (2) vertices in interior of hole regions
    holes = collections.deque()

    start = add_boundary(polygon.exterior, 0)
    for interior in polygon.interiors:
        try:
            start += add_boundary(interior, start)
        except BaseException:
            log.warning('invalid interior, continuing')
            continue

    # create clean (n,2) float array of vertices
    # and (m, 2) int array of facets
    # by stacking the sequence of (p,2) arrays
    vertices = np.vstack(vertices)
    facets = np.vstack(facets).tolist()

    # shapely polygons can include a Z component
    # strip it out for the triangulation
    if vertices.shape[1] == 3:
        vertices = vertices[:, :2]

    result = {'vertices': vertices,
              'segments': facets}
    # holes in meshpy lingo are a (h, 2) list of (x,y) points
    # which are inside the region of the hole
    # we added a hole for the exterior, which we slice away here
    holes = np.array(holes)[1:]
    if len(holes) > 0:
        result['holes'] = holes

    return result


def box(extents=None, transform=None, **kwargs):
    """
    Return a cuboid.

    Parameters
    ------------
    extents : float, or (3,) float
      Edge lengths
    transform: (4, 4) float
      Transformation matrix
    **kwargs:
        passed to Trimesh to create box

    Returns
    ------------
    geometry : trimesh.Trimesh
      Mesh of a cuboid
    """
    # vertices of the cube
    vertices = np.array([0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1,
                         1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1],
                        order='C',
                        dtype=np.float64).reshape((-1, 3))
    vertices -= 0.5

    # resize cube based on passed extents
    if extents is not None:
        extents = np.asanyarray(extents, dtype=np.float64)
        if extents.shape != (3,):
            raise ValueError('Extents must be (3,)!')
        vertices *= extents

    # hardcoded face indices
    faces = [1, 3, 0, 4, 1, 0, 0, 3, 2, 2, 4, 0, 1, 7, 3, 5, 1, 4,
             5, 7, 1, 3, 7, 2, 6, 4, 2, 2, 7, 6, 6, 5, 4, 7, 5, 6]
    faces = np.array(faces, order='C', dtype=np.int64).reshape((-1, 3))

    face_normals = [-1, 0, 0, 0, -1, 0, -1, 0, 0, 0, 0, -1, 0, 0, 1, 0, -1,
                    0, 0, 0, 1, 0, 1, 0, 0, 0, -1, 0, 1, 0, 1, 0, 0, 1, 0, 0]
    face_normals = np.asanyarray(face_normals,
                                 order='C',
                                 dtype=np.float64).reshape(-1, 3)

    box = Trimesh(vertices=vertices,
                  faces=faces,
                  face_normals=face_normals,
                  process=False,
                  **kwargs)

    # do the transform here to preserve face normals
    if transform is not None:
        box.apply_transform(transform)

    return box


def icosahedron():
    """
    Create an icosahedron, a 20 faced polyhedron.

    Returns
    -------------
    ico : trimesh.Trimesh
      Icosahederon centered at the origin.
    """
    t = (1.0 + 5.0**.5) / 2.0
    vertices = [-1, t, 0, 1, t, 0, -1, -t, 0, 1, -t, 0, 0, -1, t, 0, 1, t,
                0, -1, -t, 0, 1, -t, t, 0, -1, t, 0, 1, -t, 0, -1, -t, 0, 1]
    faces = [0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11,
             1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8,
             3, 9, 4, 3, 4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9,
             4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1]
    # scale vertices so each vertex radius is 1.0
    vertices = np.reshape(vertices, (-1, 3)) / np.sqrt(2.0 + t)
    faces = np.reshape(faces, (-1, 3))
    mesh = Trimesh(vertices=vertices,
                   faces=faces,
                   process=False)
    return mesh


def icosphere(subdivisions=3, radius=1.0, color=None):
    """
    Create an isophere centered at the origin.

    Parameters
    ----------
    subdivisions : int
      How many times to subdivide the mesh.
      Note that the number of faces will grow as function of
      4 ** subdivisions, so you probably want to keep this under ~5
    radius : float
      Desired radius of sphere
    color: (3,) float or uint8
      Desired color of sphere

    Returns
    ---------
    ico : trimesh.Trimesh
      Meshed sphere
    """
    def refine_spherical():
        vectors = ico.vertices
        scalar = (vectors ** 2).sum(axis=1)**.5
        unit = vectors / scalar.reshape((-1, 1))
        offset = radius - scalar
        ico.vertices += unit * offset.reshape((-1, 1))
    ico = icosahedron()
    ico._validate = False
    for j in range(subdivisions):
        ico = ico.subdivide()
        refine_spherical()
    ico._validate = True
    if color is not None:
        ico.visual.face_colors = color
    return ico


def uv_sphere(radius=1.0,
              count=[32, 32],
              theta=None,
              phi=None):
    """
    Create a UV sphere (latitude + longitude) centered at the
    origin. Roughly one order of magnitude faster than an
    icosphere but slightly uglier.

    Parameters
    ----------
    radius : float
      Radius of sphere
    count : (2,) int
      Number of latitude and longitude lines
    theta : (n,) float
      Optional theta angles in radians
    phi :   (n,) float
      Optional phi angles in radians

    Returns
    ----------
    mesh : trimesh.Trimesh
       Mesh of UV sphere with specified parameters
    """

    count = np.array(count, dtype=np.int)
    count += np.mod(count, 2)
    count[1] *= 2

    # generate vertices on a sphere using spherical coordinates
    if theta is None:
        theta = np.linspace(0, np.pi, count[0])
    if phi is None:
        phi = np.linspace(0, np.pi * 2, count[1])[:-1]
    spherical = np.dstack((np.tile(phi, (len(theta), 1)).T,
                           np.tile(theta, (len(phi), 1)))).reshape((-1, 2))
    vertices = util.spherical_to_vector(spherical) * radius

    # generate faces by creating a bunch of pie wedges
    c = len(theta)
    # a quad face as two triangles
    pairs = np.array([[c, 0, 1],
                      [c + 1, c, 1]])

    # increment both triangles in each quad face by the same offset
    incrementor = np.tile(np.arange(c - 1), (2, 1)).T.reshape((-1, 1))
    # create the faces for a single pie wedge of the sphere
    strip = np.tile(pairs, (c - 1, 1))
    strip += incrementor
    # the first and last faces will be degenerate since the first
    # and last vertex are identical in the two rows
    strip = strip[1:-1]

    # tile pie wedges into a sphere
    faces = np.vstack([strip + (i * c) for i in range(len(phi))])

    # poles are repeated in every strip, so a mask to merge them
    mask = np.arange(len(vertices))
    # the top pole are all the same vertex
    mask[0::c] = 0
    # the bottom pole are all the same vertex
    mask[c - 1::c] = c - 1

    # faces masked to remove the duplicated pole vertices
    # and mod to wrap to fill in the last pie wedge
    faces = mask[np.mod(faces, len(vertices))]

    # we save a lot of time by not processing again
    # since we did some bookkeeping mesh is watertight
    mesh = Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh


def capsule(height=1.0,
            radius=1.0,
            count=[32, 32]):
    """
    Create a mesh of a capsule, or a cylinder with hemispheric ends.

    Parameters
    ----------
    height : float
      Center to center distance of two spheres
    radius : float
      Radius of the cylinder and hemispheres
    count : (2,) int
      Number of sections on latitude and longitude

    Returns
    ----------
    capsule : trimesh.Trimesh
      Capsule geometry with:
        - cylinder axis is along Z
        - one hemisphere is centered at the origin
        - other hemisphere is centered along the Z axis at height
    """
    height = float(height)
    radius = float(radius)
    count = np.array(count, dtype=np.int)
    count += np.mod(count, 2)

    # create a theta where there is a double band around the equator
    # so that we can offset the top and bottom of a sphere to
    # get a nicely meshed capsule
    theta = np.linspace(0, np.pi, count[0])
    center = np.clip(np.arctan(tol.merge / radius),
                     tol.merge, np.inf)
    offset = np.array([-center, center]) + (np.pi / 2)
    theta = np.insert(theta,
                      int(len(theta) / 2),
                      offset)

    capsule = uv_sphere(radius=radius,
                        count=count,
                        theta=theta)

    top = capsule.vertices[:, 2] > tol.zero
    capsule.vertices[top] += [0, 0, height]

    return capsule


def cone(radius,
         height,
         sections=None,
         transform=None,
         **kwargs):
    """
    Create a mesh of a cone along Z centered at the origin.

    Parameters
    ----------
    radius : float
      The radius of the cylinder
    height : float
      The height of the cylinder
    sections : int or None
      How many pie wedges per revolution
    transform : (4, 4) float or None
      Transform to apply after creation
    **kwargs : dict
      Passed to Trimesh constructor

    Returns
    ----------
    cone: trimesh.Trimesh
      Resulting mesh of a cone
    """
    # create the 2D outline of a cone
    linestring = [[0, 0],
                  [radius, 0],
                  [0, height]]
    # revolve the profile to create a cone
    cone = revolve(linestring=linestring,
                   sections=sections,
                   transform=transform,
                   **kwargs)

    return cone


def cylinder(radius,
             height=None,
             sections=None,
             segment=None,
             transform=None,
             **kwargs):
    """
    Create a mesh of a cylinder along Z centered at the origin.

    Parameters
    ----------
    radius : float
      The radius of the cylinder
    height : float or None
      The height of the cylinder
    sections : int or None
      How many pie wedges should the cylinder have
    segment : (2, 3) float
      Endpoints of axis, overrides transform and height
    transform : (4, 4) float
      Transform to apply
    **kwargs:
        passed to Trimesh to create cylinder

    Returns
    ----------
    cylinder: trimesh.Trimesh
      Resulting mesh of a cylinder
    """

    if segment is not None:
        # override transform and height with the segment
        transform, height = _segment_to_cylinder(segment=segment)

    if height is None:
        raise ValueError('either `height` or `segment` must be passed!')

    half = abs(float(height)) / 2.0
    # create a profile to revolve
    linestring = [[0, -half],
                  [radius, -half],
                  [radius, half],
                  [0, half]]
    # generate cylinder through simple revolution
    return revolve(linestring=linestring,
                   sections=sections,
                   transform=transform)


def annulus(r_min,
            r_max,
            height=None,
            sections=None,
            transform=None,
            segment=None,
            **kwargs):
    """
    Create a mesh of an annular cylinder along Z centered at the origin.

    Parameters
    ----------
    r_min : float
      The inner radius of the annular cylinder
    r_max : float
      The outer radius of the annular cylinder
    height : float
      The height of the annular cylinder
    sections : int or None
      How many pie wedges should the annular cylinder have
    transform : (4, 4) float or None
      Transform to apply to move result from the origin
    segment : None or (2, 3) float
      Override transform and height with a line segment
    **kwargs:
        passed to Trimesh to create annulus

    Returns
    ----------
    annulus : trimesh.Trimesh
      Mesh of annular cylinder
    """
    if segment is not None:
        # override transform and height with the segment if passed
        transform, height = _segment_to_cylinder(segment=segment)

    if height is None:
        raise ValueError('either `height` or `segment` must be passed!')

    r_min = abs(float(r_min))
    # if center radius is zero this is a cylinder
    if r_min < tol.merge:
        return cylinder(radius=r_max,
                        height=height,
                        sections=sections,
                        transform=transform)
    r_max = abs(float(r_max))
    # we're going to center at XY plane so take half the height
    half = abs(float(height)) / 2.0
    # create counter-clockwise rectangle
    linestring = [[r_min, -half],
                  [r_max, -half],
                  [r_max, half],
                  [r_min, half],
                  [r_min, -half]]

    # revolve the curve
    annulus = revolve(linestring=linestring,
                      sections=sections,
                      transform=transform,
                      **kwargs)

    return annulus


def _segment_to_cylinder(segment):
    """
    Convert a line segment to a transform and height for a cylinder
    or cylinder-like primitive.

    Parameters
    -----------
    segment : (2, 3) float
      3D line segment in space

    Returns
    -----------
    transform : (4, 4) float
      Matrix to move a Z-extruded origin cylinder to segment
    height : float
      The height of the cylinder needed
    """
    segment = np.asanyarray(segment, dtype=np.float64)
    if segment.shape != (2, 3):
        raise ValueError('segment must be 2 3D points!')
    vector = segment[1] - segment[0]
    # override height with segment length
    height = np.linalg.norm(vector)
    # point in middle of line
    midpoint = segment[0] + (vector * 0.5)
    # align Z with our desired direction
    rotation = align_vectors([0, 0, 1], vector)
    # translate to midpoint of segment
    translation = tf.translation_matrix(midpoint)
    # compound the rotation and translation
    transform = np.dot(translation, rotation)
    return transform, height


def random_soup(face_count=100):
    """
    Return random triangles as a Trimesh

    Parameters
    -----------
    face_count : int
      Number of faces desired in mesh

    Returns
    -----------
    soup : trimesh.Trimesh
      Geometry with face_count random faces
    """
    vertices = np.random.random((face_count * 3, 3)) - 0.5
    faces = np.arange(face_count * 3).reshape((-1, 3))
    soup = Trimesh(vertices=vertices, faces=faces)
    return soup


def axis(origin_size=0.04,
         transform=None,
         origin_color=None,
         axis_radius=None,
         axis_length=None):
    """
    Return an XYZ axis marker as a  Trimesh, which represents position
    and orientation. If you set the origin size the other parameters
    will be set relative to it.

    Parameters
    ----------
    transform : (4, 4) float
      Transformation matrix
    origin_size : float
      Radius of sphere that represents the origin
    origin_color : (3,) float or int, uint8 or float
      Color of the origin
    axis_radius : float
      Radius of cylinder that represents x, y, z axis
    axis_length: float
      Length of cylinder that represents x, y, z axis

    Returns
    -------
    marker : trimesh.Trimesh
      Mesh geometry of axis indicators
    """
    # the size of the ball representing the origin
    origin_size = float(origin_size)

    # set the transform and use origin-relative
    # sized for other parameters if not specified
    if transform is None:
        transform = np.eye(4)
    if origin_color is None:
        origin_color = [255, 255, 255, 255]
    if axis_radius is None:
        axis_radius = origin_size / 5.0
    if axis_length is None:
        axis_length = origin_size * 10.0

    # generate a ball for the origin
    axis_origin = uv_sphere(radius=origin_size,
                            count=[10, 10])
    axis_origin.apply_transform(transform)

    # apply color to the origin ball
    axis_origin.visual.face_colors = origin_color

    # create the cylinder for the z-axis
    translation = tf.translation_matrix(
        [0, 0, axis_length / 2])
    z_axis = cylinder(
        radius=axis_radius,
        height=axis_length,
        transform=transform.dot(translation))
    # XYZ->RGB, Z is blue
    z_axis.visual.face_colors = [0, 0, 255]

    # create the cylinder for the y-axis
    translation = tf.translation_matrix(
        [0, 0, axis_length / 2])
    rotation = tf.rotation_matrix(np.radians(-90),
                                  [1, 0, 0])
    y_axis = cylinder(
        radius=axis_radius,
        height=axis_length,
        transform=transform.dot(rotation).dot(translation))
    # XYZ->RGB, Y is green
    y_axis.visual.face_colors = [0, 255, 0]

    # create the cylinder for the x-axis
    translation = tf.translation_matrix(
        [0, 0, axis_length / 2])
    rotation = tf.rotation_matrix(np.radians(90),
                                  [0, 1, 0])
    x_axis = cylinder(
        radius=axis_radius,
        height=axis_length,
        transform=transform.dot(rotation).dot(translation))
    # XYZ->RGB, X is red
    x_axis.visual.face_colors = [255, 0, 0]

    # append the sphere and three cylinders
    marker = util.concatenate([axis_origin,
                               x_axis,
                               y_axis,
                               z_axis])
    return marker


def camera_marker(camera,
                  marker_height=0.4,
                  origin_size=None):
    """
    Create a visual marker for a camera object, including an axis and FOV.

    Parameters
    ---------------
    camera : trimesh.scene.Camera
      Camera object with FOV and transform defined
    marker_height : float
      How far along the camera Z should FOV indicators be
    origin_size : float
      Sphere radius of the origin (default: marker_height / 10.0)

    Returns
    ------------
    meshes : list
      Contains Trimesh and Path3D objects which can be visualized
    """

    # create sane origin size from marker height
    if origin_size is None:
        origin_size = marker_height / 10.0

    # append the visualizations to an array
    meshes = [axis(origin_size=origin_size)]

    try:
        # path is a soft dependency
        from .path.exchange.load import load_path
    except ImportError:
        # they probably don't have shapely installed
        log.warning('unable to create FOV visualization!',
                    exc_info=True)
        return meshes

    # calculate vertices from camera FOV angles
    x = marker_height * np.tan(np.deg2rad(camera.fov[0]) / 2.0)
    y = marker_height * np.tan(np.deg2rad(camera.fov[1]) / 2.0)
    z = marker_height

    # combine the points into the vertices of an FOV visualization
    points = np.array(
        [(0, 0, 0),
         (-x, -y, z),
         (x, -y, z),
         (x, y, z),
         (-x, y, z)],
        dtype=float)

    # create line segments for the FOV visualization
    # a segment from the origin to each bound of the FOV
    segments = np.column_stack(
        (np.zeros_like(points), points)).reshape(
        (-1, 3))

    # add a loop for the outside of the FOV then reshape
    # the whole thing into multiple line segments
    segments = np.vstack((segments,
                          points[[1, 2,
                                  2, 3,
                                  3, 4,
                                  4, 1]])).reshape((-1, 2, 3))

    # add a single Path3D object for all line segments
    meshes.append(load_path(segments))

    return meshes


def truncated_prisms(tris, origin=None, normal=None):
    """
    Return a mesh consisting of multiple watertight prisms below
    a list of triangles, truncated by a specified plane.

    Parameters
    -------------
    triangles : (n, 3, 3) float
      Triangles in space
    origin : None or (3,) float
      Origin of truncation plane
    normal : None or (3,) float
      Unit normal vector of truncation plane

    Returns
    -----------
    mesh : trimesh.Trimesh
      Triangular mesh
    """
    if origin is None:
        transform = np.eye(4)
    else:
        transform = plane_transform(origin=origin, normal=normal)

    # transform the triangles to the specified plane
    transformed = tf.transform_points(
        tris.reshape((-1, 3)), transform).reshape((-1, 9))

    # stack triangles such that every other one is repeated
    vs = np.column_stack((transformed, transformed)).reshape((-1, 3, 3))
    # set the Z value of the second triangle to zero
    vs[1::2, :, 2] = 0
    # reshape triangles to a flat array of points and transform back to original frame
    vertices = tf.transform_points(
        vs.reshape((-1, 3)), matrix=np.linalg.inv(transform))

    # face indexes for a *single* truncated triangular prism
    f = np.array([[2, 1, 0],
                  [3, 4, 5],
                  [0, 1, 4],
                  [1, 2, 5],
                  [2, 0, 3],
                  [4, 3, 0],
                  [5, 4, 1],
                  [3, 5, 2]])
    # find the projection of each triangle with the normal vector
    cross = np.dot([0, 0, 1], triangles.cross(transformed.reshape((-1, 3, 3))).T)
    # stack faces into one prism per triangle
    f_seq = np.tile(f, (len(transformed), 1)).reshape((-1, len(f), 3))
    # if the normal of the triangle was positive flip the winding
    f_seq[cross > 0] = np.fliplr(f)
    # offset stacked faces to create correct indices
    faces = (f_seq + (np.arange(len(f_seq)) * 6).reshape((-1, 1, 1))).reshape((-1, 3))

    # create a mesh from the data
    mesh = Trimesh(vertices=vertices, faces=faces, process=False)

    return mesh
