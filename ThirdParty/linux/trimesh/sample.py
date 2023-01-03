"""
sample.py
------------

Randomly sample surface and volume of meshes.
"""
import numpy as np

from . import util
from . import transformations


def sample_surface(mesh, count):
    """
    Sample the surface of a mesh, returning the specified
    number of points

    For individual triangle sampling uses this method:
    http://mathworld.wolfram.com/TrianglePointPicking.html

    Parameters
    ---------
    mesh : trimesh.Trimesh
      Geometry to sample the surface of
    count : int
      Number of points to return

    Returns
    ---------
    samples : (count, 3) float
      Points in space on the surface of mesh
    face_index : (count,) int
      Indices of faces for each sampled point
    """

    # len(mesh.faces) float, array of the areas
    # of each face of the mesh
    area = mesh.area_faces
    # total area (float)
    area_sum = np.sum(area)
    # cumulative area (len(mesh.faces))
    area_cum = np.cumsum(area)
    face_pick = np.random.random(count) * area_sum
    face_index = np.searchsorted(area_cum, face_pick)

    # pull triangles into the form of an origin + 2 vectors
    tri_origins = mesh.triangles[:, 0]
    tri_vectors = mesh.triangles[:, 1:].copy()
    tri_vectors -= np.tile(tri_origins, (1, 2)).reshape((-1, 2, 3))

    # pull the vectors for the faces we are going to sample from
    tri_origins = tri_origins[face_index]
    tri_vectors = tri_vectors[face_index]

    # randomly generate two 0-1 scalar components to multiply edge vectors by
    random_lengths = np.random.random((len(tri_vectors), 2, 1))

    # points will be distributed on a quadrilateral if we use 2 0-1 samples
    # if the two scalar components sum less than 1.0 the point will be
    # inside the triangle, so we find vectors longer than 1.0 and
    # transform them to be inside the triangle
    random_test = random_lengths.sum(axis=1).reshape(-1) > 1.0
    random_lengths[random_test] -= 1.0
    random_lengths = np.abs(random_lengths)

    # multiply triangle edge vectors by the random lengths and sum
    sample_vector = (tri_vectors * random_lengths).sum(axis=1)

    # finally, offset by the origin to generate
    # (n,3) points in space on the triangle
    samples = sample_vector + tri_origins

    return samples, face_index


def volume_mesh(mesh, count):
    """
    Use rejection sampling to produce points randomly
    distributed in the volume of a mesh.


    Parameters
    ---------
    mesh : trimesh.Trimesh
      Geometry to sample
    count : int
      Number of points to return

    Returns
    ---------
    samples : (n, 3) float
      Points in the volume of the mesh where n <= count
    """
    points = (np.random.random((count, 3)) * mesh.extents) + mesh.bounds[0]
    contained = mesh.contains(points)
    samples = points[contained][:count]
    return samples


def volume_rectangular(extents,
                       count,
                       transform=None):
    """
    Return random samples inside a rectangular volume,
    useful for sampling inside oriented bounding boxes.

    Parameters
    ----------
    extents :   (3,) float
      Side lengths of rectangular solid
    count : int
      Number of points to return
    transform : (4, 4) float
      Homogeneous transformation matrix

    Returns
    ---------
    samples : (count, 3) float
      Points in requested volume
    """
    samples = np.random.random((count, 3)) - .5
    samples *= extents
    if transform is not None:
        samples = transformations.transform_points(samples,
                                                   transform)
    return samples


def sample_surface_even(mesh, count, radius=None):
    """
    Sample the surface of a mesh, returning samples which are
    VERY approximately evenly spaced. This is accomplished by
    sampling and then rejecting pairs that are too close together.

    Note that since it is using rejection sampling it may return
    fewer points than requested (i.e. n < count). If this is the
    case a log.warning will be emitted.

    Parameters
    ---------
    mesh : trimesh.Trimesh
      Geometry to sample the surface of
    count : int
      Number of points to return
    radius : None or float
      Removes samples below this radius

    Returns
    ---------
    samples : (n, 3) float
      Points in space on the surface of mesh
    face_index : (n,) int
      Indices of faces for each sampled point
    """
    from .points import remove_close

    # guess radius from area
    if radius is None:
        radius = np.sqrt(mesh.area / (3 * count))

    # get points on the surface
    points, index = sample_surface(mesh, count * 3)

    # remove the points closer than radius
    points, mask = remove_close(points, radius)

    # we got all the samples we expect
    if len(points) >= count:
        return points[:count], index[mask][:count]

    # warn if we didn't get all the samples we expect
    util.log.warning('only got {}/{} samples!'.format(
        len(points), count))

    return points, index[mask]


def sample_surface_sphere(count):
    """
    Correctly pick random points on the surface of a unit sphere

    Uses this method:
    http://mathworld.wolfram.com/SpherePointPicking.html

    Parameters
    ----------
    count : int
      Number of points to return

    Returns
    ----------
    points : (count, 3) float
      Random points on the surface of a unit sphere
    """
    # get random values 0.0-1.0
    u, v = np.random.random((2, count))
    # convert to two angles
    theta = np.pi * 2 * u
    phi = np.arccos((2 * v) - 1)
    # convert spherical coordinates to cartesian
    points = util.spherical_to_vector(
        np.column_stack((theta, phi)))
    return points
