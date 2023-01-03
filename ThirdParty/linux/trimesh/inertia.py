"""
inertia.py
-------------

Functions for dealing with inertia tensors.

Results validated against known geometries and checked for
internal consistency.
"""

import numpy as np

from . import util

# a matrix where all non- diagonal terms are -1.0
# and all diagonal terms are 1.0
negate_nondiagonal = (np.eye(3, dtype=np.float64) * 2) - 1


def cylinder_inertia(mass, radius, height, transform=None):
    """
    Return the inertia tensor of a cylinder.

    Parameters
    ------------
    mass : float
      Mass of cylinder
    radius : float
      Radius of cylinder
    height : float
      Height of cylinder
    transform : (4, 4) float
      Transformation of cylinder

    Returns
    ------------
    inertia : (3, 3) float
      Inertia tensor
    """
    h2, r2 = height ** 2, radius ** 2
    diagonal = np.array([((mass * h2) / 12) + ((mass * r2) / 4),
                         ((mass * h2) / 12) + ((mass * r2) / 4),
                         (mass * r2) / 2])
    inertia = diagonal * np.eye(3)

    if transform is not None:
        inertia = transform_inertia(transform, inertia)

    return inertia


def sphere_inertia(mass, radius):
    """
    Return the inertia tensor of a sphere.

    Parameters
    ------------
    mass : float
      Mass of sphere
    radius : float
      Radius of sphere

    Returns
    ------------
    inertia : (3, 3) float
      Inertia tensor
    """
    inertia = (2.0 / 5.0) * (radius ** 2) * mass * np.eye(3)
    return inertia


def principal_axis(inertia):
    """
    Find the principal components and principal axis
    of inertia from the inertia tensor.

    Parameters
    ------------
    inertia : (3, 3) float
      Inertia tensor

    Returns
    ------------
    components : (3,) float
      Principal components of inertia
    vectors : (3, 3) float
      Row vectors pointing along the
      principal axes of inertia
    """
    inertia = np.asanyarray(inertia, dtype=np.float64)
    if inertia.shape != (3, 3):
        raise ValueError('inertia tensor must be (3, 3)!')

    # you could any of the following to calculate this:
    # np.linalg.svd, np.linalg.eig, np.linalg.eigh
    # moment of inertia is square symmetric matrix
    # eigh has the best numeric precision in tests
    components, vectors = np.linalg.eigh(inertia * negate_nondiagonal)

    # eigh returns them as column vectors, change them to row vectors
    vectors = vectors.T

    return components, vectors


def transform_inertia(transform, inertia_tensor):
    """
    Transform an inertia tensor to a new frame.

    More details in OCW PDF:
    MIT16_07F09_Lec26.pdf

    Parameters
    ------------
    transform : (3, 3) or (4, 4) float
      Transformation matrix
    inertia_tensor : (3, 3) float
      Inertia tensor

    Returns
    ------------
    transformed : (3, 3) float
      Inertia tensor in new frame
    """
    # check inputs and extract rotation
    transform = np.asanyarray(transform, dtype=np.float64)
    if transform.shape == (4, 4):
        rotation = transform[:3, :3]
    elif transform.shape == (3, 3):
        rotation = transform
    else:
        raise ValueError('transform must be (3, 3) or (4, 4)!')

    inertia_tensor = np.asanyarray(inertia_tensor, dtype=np.float64)
    if inertia_tensor.shape != (3, 3):
        raise ValueError('inertia_tensor must be (3, 3)!')

    transformed = util.multi_dot([rotation,
                                  inertia_tensor * negate_nondiagonal,
                                  rotation.T])
    transformed *= negate_nondiagonal
    return transformed


def radial_symmetry(mesh):
    """
    Check whether a mesh has radial symmetry.

    Returns
    -----------
    symmetry : None or str
         None         No rotational symmetry
         'radial'     Symmetric around an axis
         'spherical'  Symmetric around a point
    axis : None or (3,) float
      Rotation axis or point
    section : None or (3, 2) float
      If radial symmetry provide vectors
      to get cross section
    """

    # shortcuts to avoid typing and hitting cache
    scalar = mesh.principal_inertia_components
    vector = mesh.principal_inertia_vectors
    # the sorted order of the principal components
    order = scalar.argsort()

    # we are checking if a geometry has radial symmetry
    # if 2 of the PCI are equal, it is a revolved 2D profile
    # if 3 of the PCI (all of them) are equal it is a sphere
    # thus we take the diff of the sorted PCI, scale it as a ratio
    # of the largest PCI, and then scale to the tolerance we care about
    # if tol is 1e-3, that means that 2 components are identical if they
    # are within .1% of the maximum PCI.
    diff = np.abs(np.diff(scalar[order]))
    diff /= np.abs(scalar).max()
    # diffs that are within tol of zero
    diff_zero = (diff / 1e-3).astype(int) == 0

    if diff_zero.all():
        # this is the case where all 3 PCI are identical
        # this means that the geometry is symmetric about a point
        # examples of this are a sphere, icosahedron, etc
        axis = vector[0]
        section = vector[1:]

        return 'spherical', axis, section

    elif diff_zero.any():
        # this is the case for 2/3 PCI are identical
        # this means the geometry is symmetric about an axis
        # probably a revolved 2D profile

        # we know that only 1/2 of the diff values are True
        # if the first diff is 0, it means if we take the first element
        # in the ordered PCI we will have one of the non- revolve axis
        # if the second diff is 0, we take the last element of
        # the ordered PCI for the section axis
        # if we wanted the revolve axis we would just switch [0,-1] to
        # [-1,0]

        # since two vectors are the same, we know the middle
        # one is one of those two
        section_index = order[np.array([[0, 1],
                                        [1, -1]])[diff_zero]].flatten()
        section = vector[section_index]

        # we know the rotation axis is the sole unique value
        # and is either first or last of the sorted values
        axis_index = order[np.array([-1, 0])[diff_zero]][0]
        axis = vector[axis_index]
        return 'radial', axis, section

    return None, None, None
