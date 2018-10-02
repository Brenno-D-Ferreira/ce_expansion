#!/usr/bin/env python

import pandas
import numpy as np


def calculate_gamma(element1: str,
                    element2: str,
                    exp: "Filename for experimental data" = "data/experimental_hbe.csv",
                    est: "Filename for theoretical data" = "data/estimated_hbe.csv") -> "tuple":
    """
    Given a pair of elements: "element1" and "element2", this function calculates the gamma coefficient from Yan et al.

    :param element1: The first element in the bimetallic pair
    :type element1: str
    :param element2: The second element in the bimetallic pair
    :type element2: str
    :param exp: Experimental bond dissociation energies. This is the preferred source of data.
    :type exp: str
    :param est: Theoretical bond dissociation energies. If no experiment is available, we get our data from here.
    :type est: str

    :return: The two gamma coefficients as two floats inside a tuple, in the order the two elements were provided.
             In other words, calling the function with element1 = "Cu" and element2 = "Ag" would return a tuple where
             the first entry is the gamma coefficient for Cu, and the second entry is the gamma coefficient for Ag.
    """

    # Early exit condition: if both metals are the same, gamma is 1
    if element1 == element2:
        return 1.0, 1.0

    # Get our bond dissociation energies into a dictionary and put them into a set of variables
    bde_table = csv_to_dict(exp)
    if bde_table[element1][element2] is None:
        bde_table = csv_to_dict(est)
    elif bde_table[element1][element1] is None or bde_table[element2][element2] is None:
        bde_table = csv_to_dict(est)
    bde_mono1 = float(bde_table[element1][element1])  # Element1 - Element1 bond dissociation energy
    bde_mono2 = float(bde_table[element2][element2])  # Element2 - Element2 bond dissociation energy
    bde_hetero = float(bde_table[element1][element2])  # Element1 - Element2 bond dissociation energy

    # Solve the system of linear equations
    # These equations come from Equations 5 and 6 in the Bond-Centric Model of Yan et. al.
    gamma_values = np.linalg.solve([[bde_mono1, bde_mono2], [1, 1]],
                                   [[2 * bde_hetero], [2]])

    return float(gamma_values[0]), float(gamma_values[1])