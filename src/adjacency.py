#!/usr/bin/env python3

import pickle

import ase.neighborlist
import numpy as np

DEFAULT_ELEMENTS = ("Cu", "Cu")
DEFAULT_RADIUS = 2.8
with open("../data/precalc_coeffs.pickle", "rb") as precalcs:
    DEFAULT_BOND_COEFFS = pickle.load(precalcs)


def buildAdjacencyMatrix(atoms_object: "ase.Atoms",
                         radius_dictionary: "dict" = {DEFAULT_ELEMENTS: DEFAULT_RADIUS}) -> "np.ndarray":
    """
    Sparse matrix representation from an ase atoms object.

    Args:
    atoms_object (ase.Atoms): An ASE atoms object representing the system of interest
    radius_dictionary (dict): A dictionary with the atom-atom radii at-which a bond is considered a
                              bond. If no dict is supplied, Cu-Cu bonds of max-len 2.8 are assumed.

    Returns:
    np.ndarray : A numpy array representing the sparse matrix of the ase object
    """
    # Construct the list of bonds
    sources, destinations = ase.neighborlist.neighbor_list("ij", atoms_object, radius_dictionary)
    # Generate the matrix
    adjacency_matrix = np.zeros((len(atoms_object), len(atoms_object)))
    for bond in zip(sources, destinations):
        adjacency_matrix[bond[0], bond[1]] += 1

    return adjacency_matrix


def buildAdjacencyList(atoms_object: "ase.Atoms",
                       radius_dictionary: "dict" = {DEFAULT_ELEMENTS: DEFAULT_RADIUS}) -> "np.ndarray":
    """
      Adjacency list representation for an ase atoms object.


      atoms_object (ase.Atoms): An ASE atoms object representing the system of interest
      radius_dictionary (dict): A dictionary with the atom-atom radii at-which a bond is considered a
                                bond. If no dict is supplied, Cu-Cu bonds of max-len 2.8 are assumed.

      Returns:
      np.ndarray : A numpy array representing the adjacency list of the ase object

    """

    # Construct the list of bonds
    sources, destinations = ase.neighborlist.neighbor_list("ij", atoms_object, radius_dictionary)
    # Sort along our destinations
    # Mergesort has a slightly better worst-case time complexity than quicksort or heapsort, and is stable
    sorted_destinations = destinations[sources.argsort(kind='mergesort')]

    # Figure out how the list of bonds will be sliced, and slice it
    bins = np.bincount(sources)
    splitting = np.zeros(len(bins), dtype=int)
    for count, item in enumerate(bins):
        if count == 0:
            splitting[count] = item
        else:
            splitting[count] = item + splitting[count - 1]

    # Slice the list of bonds to get the adjacency list
    adjacency_list = np.split(sorted_destinations, splitting)

    # Check that the final entry is an empty list, otherwise something weird happened
    if len(adjacency_list[-1]) != 0:
        raise ValueError(
            "The following atoms have bonds yet do not appear to be bound to any item: " + str(adjacency_list[-1]))
    else:
        return np.delete(adjacency_list, -1)