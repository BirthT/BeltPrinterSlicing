"""
voxel.py
-----------

Convert meshes to a simple voxel data structure and back again.
"""
import numpy as np

from . import ops
from . import transforms
from . import morphology
from . import encoding as enc

from .. import bounds as bounds_module
from .. import caching
from .. import transformations as tr

from ..parent import Geometry
from ..constants import log


class VoxelGrid(Geometry):
    """
    Store 3D voxels.
    """

    def __init__(self, encoding, transform=None, metadata=None):
        if transform is None:
            transform = np.eye(4)
        if isinstance(encoding, np.ndarray):
            encoding = enc.DenseEncoding(encoding.astype(bool))
        if encoding.dtype != bool:
            raise ValueError('encoding must have dtype bool')
        self._data = caching.DataStore()
        self.encoding = encoding
        self._data['transform'] = transforms.Transform(transform)
        self._cache = caching.Cache(id_function=self._data.crc)

        self.metadata = dict()
        # update the mesh metadata with passed metadata
        if isinstance(metadata, dict):
            self.metadata.update(metadata)
        elif metadata is not None:
            raise ValueError(
                'metadata should be a dict or None, got %s' % str(metadata))

    def md5(self):
        return self._data.md5()

    def crc(self):
        return self._data.crc()

    @property
    def encoding(self):
        """
        `Encoding` object providing the occupancy grid.

        See `trimesh.voxel.encoding` for implementations.
        """
        return self._data['encoding']

    @encoding.setter
    def encoding(self, encoding):
        if isinstance(encoding, np.ndarray):
            encoding = enc.DenseEncoding(encoding)
        elif not isinstance(encoding, enc.Encoding):
            raise ValueError(
                'encoding must be an Encoding, got %s' % str(encoding))
        if len(encoding.shape) != 3:
            raise ValueError(
                'encoding must be rank 3, got shape %s' % str(encoding.shape))
        if encoding.dtype != bool:
            raise ValueError(
                'encoding must be binary, got %s' % encoding.dtype)
        self._data['encoding'] = encoding

    @property
    def _transform(self):
        return self._data['transform']

    @property
    def transform(self):
        """4x4 homogeneous transformation matrix."""
        return self._transform.matrix

    @transform.setter
    def transform(self, matrix):
        """4x4 homogeneous transformation matrix."""
        self._transform.matrix = matrix

    @property
    def translation(self):
        """Location of voxel at [0, 0, 0]."""
        return self._transform.translation

    @property
    def origin(self):
        """Deprecated. Use `self.translation`."""
        # DEPRECATED. Use translation instead
        return self.translation

    @property
    def scale(self):
        """
        3-element float representing per-axis scale.

        Raises a `RuntimeError` if `self.transform` has rotation or
        shear components.
        """
        return self._transform.scale

    @property
    def pitch(self):
        """
        Uniform scaling factor representing the side length of
        each voxel.

        Returns
        -----------
        pitch : float
          Pitch of the voxels.

        Raises
        ------------
        `RuntimeError`
          If `self.transformation` has rotation or shear
          components of has non-uniform scaling.
        """
        return self._transform.pitch

    @property
    def element_volume(self):
        return self._transform.unit_volume

    def apply_transform(self, matrix):
        self._transform.apply_transform(matrix)
        return self

    def strip(self):
        """
        Mutate self by stripping leading/trailing planes of zeros.

        Returns
        --------
        self after mutation occurs in-place
        """
        encoding, padding = self.encoding.stripped
        self.encoding = encoding
        self._transform.matrix[:3, 3] = self.indices_to_points(padding[:, 0])
        return self

    @caching.cache_decorator
    def bounds(self):
        indices = self.sparse_indices
        # get all 8 corners of the AABB
        corners = bounds_module.corners([indices.min(axis=0) - 0.5,
                                         indices.max(axis=0) + 0.5])
        # transform these corners to a new frame
        corners = self._transform.transform_points(corners)
        # get the AABB of corners in-frame
        bounds = np.array([corners.min(axis=0), corners.max(axis=0)])
        bounds.flags.writeable = False
        return bounds

    @caching.cache_decorator
    def extents(self):
        bounds = self.bounds
        extents = bounds[1] - bounds[0]
        extents.flags.writeable = False
        return extents

    @caching.cache_decorator
    def is_empty(self):
        return self.encoding.is_empty

    @property
    def shape(self):
        """3-tuple of ints denoting shape of occupancy grid."""
        return self.encoding.shape

    @caching.cache_decorator
    def filled_count(self):
        """int, number of occupied voxels in the grid."""
        return self.encoding.sum.item()

    def is_filled(self, point):
        """
        Query points to see if the voxel cells they lie in are
        filled or not.

        Parameters
        ----------
        point : (n, 3) float
          Points in space

        Returns
        ---------
        is_filled : (n,) bool
          Is cell occupied or not for each point
        """
        point = np.asanyarray(point)
        indices = self.points_to_indices(point)
        in_range = np.logical_and(
            np.all(indices < np.array(self.shape), axis=-1),
            np.all(indices >= 0, axis=-1))

        is_filled = np.zeros_like(in_range)
        is_filled[in_range] = self.encoding.gather_nd(indices[in_range])
        return is_filled

    def fill(self, method='holes', **kwargs):
        """
        Mutates self by filling in the encoding according to `morphology.fill`.

        Parameters
        ----------
        method: implementation key, one of
            `trimesh.voxel.morphology.fill.fillers` keys
        **kwargs: additional kwargs passed to the keyed implementation

        Returns
        ----------
        self after replacing encoding with a filled version.
        """
        self.encoding = morphology.fill(self.encoding, method=method, **kwargs)
        return self

    def hollow(self, structure=None):
        """
        Mutates self by removing internal voxels leaving only surface elements.

        Surviving elements are those in encoding that are adjacent to an empty
        voxel, where adjacency is controlled by `structure`.

        Parameters
        ----------
        structure: adjacency structure. If None, square connectivity is used.

        Returns
        ----------
        self after replacing encoding with a surface version.
        """
        self.encoding = morphology.surface(self.encoding)
        return self

    @caching.cache_decorator
    def marching_cubes(self):
        """
        A marching cubes Trimesh representation of the voxels.

        No effort was made to clean or smooth the result in any way;
        it is merely the result of applying the scikit-image
        measure.marching_cubes function to self.encoding.dense.

        Returns
        ---------
        meshed: Trimesh object representing the current voxel
                        object, as returned by marching cubes algorithm.
        """
        meshed = ops.matrix_to_marching_cubes(matrix=self.matrix)
        return meshed

    @property
    def matrix(self):
        """
        Return a DENSE matrix of the current voxel encoding

        Returns
        -------------
        dense : (a, b, c) bool
          Numpy array of dense matrix
          Shortcut to voxel.encoding.dense
        """
        return self.encoding.dense

    @caching.cache_decorator
    def volume(self):
        """
        What is the volume of the filled cells in the current voxel object.

        Returns
        ---------
        volume: float, volume of filled cells
        """
        return self.filled_count * self.element_volume

    @caching.cache_decorator
    def points(self):
        """
        The center of each filled cell as a list of points.

        Returns
        ----------
        points: (self.filled, 3) float, list of points
        """
        return self._transform.transform_points(
            self.sparse_indices.astype(float))

    @property
    def sparse_indices(self):
        """(n, 3) int array of sparse indices of occupied voxels."""
        return self.encoding.sparse_indices

    def as_boxes(self, colors=None, **kwargs):
        """
        A rough Trimesh representation of the voxels with a box
        for each filled voxel.

        Parameters
        ----------
        colors : (3,) or (4,) float or uint8
                 (X, Y, Z, 3) or (X, Y, Z, 4) float or uint8
         Where matrix.shape == (X, Y, Z)

        Returns
        ---------
        mesh : trimesh.Trimesh
          Mesh with one box per filled cell.
        """

        if colors is not None:
            colors = np.asanyarray(colors)
            if colors.ndim == 4:
                encoding = self.encoding
                if colors.shape[:3] == encoding.shape:
                    # TODO jackd: more efficient implementation?
                    # encoding.as_mask?
                    colors = colors[encoding.dense]
                else:
                    log.warning('colors incorrect shape!')
                    colors = None
            elif colors.shape not in ((3,), (4,)):
                log.warning('colors incorrect shape!')
                colors = None

        mesh = ops.multibox(
            centers=self.sparse_indices.astype(float), colors=colors)

        mesh = mesh.apply_transform(self.transform)
        return mesh

    def points_to_indices(self, points):
        """
        Convert points to indices in the matrix array.

        Parameters
        ----------
        points: (n, 3) float, point in space

        Returns
        ---------
        indices: (n, 3) int array of indices into self.encoding
        """
        points = self._transform.inverse_transform_points(points)
        return np.round(points).astype(int)

    def indices_to_points(self, indices):
        return self._transform.transform_points(indices.astype(float))

    def show(self, *args, **kwargs):
        """
        Convert the current set of voxels into a trimesh for visualization
        and show that via its built- in preview method.
        """
        return self.as_boxes(kwargs.pop(
            'colors', None)).show(*args, **kwargs)

    def copy(self):
        return VoxelGrid(self.encoding.copy(),
                         self._transform.matrix.copy())

    def revoxelized(self, shape):
        """
        Create a new VoxelGrid without rotations, reflections or shearing.

        Parameters
        ----------
        shape: 3-tuple of ints denoting the shape of the returned VoxelGrid.

        Returns
        ----------
        VoxelGrid of the given shape with (possibly non-uniform) scale and
        translation transformation matrix.
        """
        from .. import util
        shape = tuple(shape)
        bounds = self.bounds.copy()
        extents = self.extents
        points = util.grid_linspace(bounds, shape).reshape(shape + (3,))
        dense = self.is_filled(points)
        scale = extents / np.asanyarray(shape)
        translate = bounds[0]
        return VoxelGrid(
            dense,
            transform=tr.scale_and_translate(scale, translate))

    def __add__(self, other):
        raise NotImplementedError("TODO : implement voxel concatenation")
