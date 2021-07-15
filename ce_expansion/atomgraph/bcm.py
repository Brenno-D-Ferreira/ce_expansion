import itertools
import collections.abc

import numpy as np
import ase.units

from ce_expansion.atomgraph import adjacency
from ce_expansion.data.gamma import GammaValues


def recursive_update(d, u):
    """
    recursively updates 'dict of dicts'
    Ex)
    d = {0: {1: 2}}
    u = {0: {3: 4}, 8: 9}

    recursive_update(d, u) == {0: {1: 2, 3: 4}, 8: 9}

    Args:
    d (dict): the nested dict object to update
    u (dict): the nested dict that contains new key-value pairs

    Returns:
    d (dict): the final updated dict
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = recursive_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class BCModel:
    def __init__(self, atoms, metal_types=None, bond_list=None):
        """
        Based on metal_types, create ce_bulk and gamma dicts from the data given

        Args:
        atoms: ASE atoms object which contains the data of the NP being tested
        bond_list: list of atom indices involved in each bond

        KArgs:
            metal_types: List of metals found within the nano-particle
                - If not passed, will use elements provided by the atoms object
        """

        self.atoms = atoms.copy()
        self.atoms.pbc = False

        if metal_types is None:
            # get metal_types from atoms object
            self.metal_types = sorted(set(atoms.symbols))
        else:
            # ensure metal_types to unique, sorted list of metals
            self.metal_types = sorted(set(m.title() for m in metal_types))

        self.bond_list = bond_list
        if self.bond_list is None:
            self.bond_list = adjacency.build_bonds_arr(self.atoms)

        self.cn = np.bincount(self.bond_list[:, 0])

        # creating gamma list for every possible atom pairing
        self.gamma = None
        self.ce_bulk = None
        self._get_bcm_params()

        # get bonded atom columns
        self.a1 = self.bond_list[:, 0]
        self.a2 = self.bond_list[:, 1]

        # Calculate and set the precomps matrix
        self.precomps = None
        self.precomps = self._calc_precomps()
        self.cn_precomps = np.sqrt(self.cn * 12)[self.a1]

    def __len__(self):
        return len(self.atoms)

    def _get_bcm_params(self):
        """
            Creates gamma and ce_bulk dictionaries which are then used to created precomputed values for the BCM calculation

        Sets:   Gamma: Weighting factors of the computed elements within the BCM
                ce_bulk: Bulk Cohesive energy values

        """
        gamma = {}
        ce_bulk = {}
        for item in itertools.combinations_with_replacement(self.metal_types, 2):
            # Casting metals and setting keys for dictionary
            metal_1, metal_2 = item

            gamma_obj = GammaValues(metal_1, metal_2)

            # using Update function to create clean Gamma an bulk dictionaries
            gamma = recursive_update(gamma, gamma_obj.gamma)
            # add ce_bulk vals
            ce_bulk[gamma_obj.element_a] = gamma_obj.ce_a
            ce_bulk[gamma_obj.element_b] = gamma_obj.ce_b

        self.ce_bulk = ce_bulk
        self.gammas = gamma

    def _calc_precomps(self):
        """
            Uses the Gamma and ce_bulk dictionaries to create a precomputed BCM matrix of gammas and ce_bulk values

            [precomps] = [gamma of element 1] * [ce_bulk of element 1 to element 2]

        Returns: Precomp Matrix

        """
        # precompute values for BCM calc
        n_met = len(self.metal_types)

        precomps = np.ones((n_met, n_met))

        for i in range(n_met):
            for j in range(n_met):

                M1 = self.metal_types[i]
                M2 = self.metal_types[j]
                precomp_bulk = self.ce_bulk[M1]
                precomp_gamma = self.gammas[M1][M2]

                precomps[i, j] = precomp_gamma * precomp_bulk
        return precomps

    def calc_ce(self, orderings):
        """
        Calculates the Cohesive energy of the ordering given or of the default ordering of the NP

        [Cohesive Energy] = ( [precomp values of element A and B] / sqrt(12 * CN) ) / [num atoms]

        Args:
            orderings: The ordering of atoms within the NP; ordering key is based on Metals in alphabetical order
                - Will use ardering defined by atom if not given an ordering

        Returns: Cohesive Energy
        """
        return (self.precomps[orderings[self.a1], orderings[self.a2]] / self.cn_precomps).sum() / len(self.atoms)

    def calc_ee(self, orderings):
        """
            Calculates the Excess energy of the ordering given or of the default ordering of the NP

            [Excess Energy] = [CE of NP] - sum([Pure Element NP] * [Comp of Element in NP])

        Args:
            orderings: The ordering of atoms within the NP; ordering key is based on Metals in alphabetical order

        Returns: Excess Energy

        """

        metals = np.bincount(orderings)

        #Obtain atom fractions of each tested element
        x_i =  metals / len(orderings)

        #Calculate energy of tested NP first;
        ee = self.calc_ce(orderings)

       # Then, subtract calculated pure NP energies multiplied by respective fractions to get Excess Energy
        for ele in range(len(metals)):
            x_ele = x_i[ele]
            o_mono_x = np.ones(len(self), int) * ele

            ee -= self.calc_ce(o_mono_x) * x_ele
        return(ee)

    def calc_smix(self, orderings):
        """

        Uses boltzman constant, orderings, and element compositions to determine the smix of the nanoparticle

        Args:
            orderings: The ordering of atoms within the NP; ordering key is based on Metals in alphabetical order

        Returns: entropy of mixing (smix)

        """

        x_i = np.bincount(orderings) / len(orderings)

        # drop 0s to avoid errors
        x_i = x_i[x_i != 0]

        kb = ase.units.kB

        smix = -kb * sum(x_i * np.log(x_i))

        return smix

    def calc_gmix(self, orderings, T=298):
        """

        gmix = self.ee - T * self.calc_smix(ordering)

        Args:
            T: Temperature of the system in Kelvin; Defaults at room temp of 25 C
            orderings: The ordering of atoms within the NP; ordering key is based on Metals in alphabetical order

        Returns: free energy of mixing (gmix)

        """

        gmix = self.calc_ee(orderings) - T * self.calc_smix(orderings)

        return gmix

    def metropolis(self, ordering,
                   num_steps=1000,
                   swap_any=False):
        '''
        Metropolis-Hastings-based exploration of similar NPs

        Args:
        atomgraph (atomgraph.AtomGraph) : An atomgraph representing the NP
        ordering (np.array) : 1D chemical ordering array
        num_steps (int) : How many steps to simulate for
        swap_any (bool) : Determines whether to restrict the algorithm's swaps
                          to only atoms directly bound to  the atom of interest.
                          If set to 'True', the algorithm chooses any two atoms
                          in the NP regardless of where they are. Selecting
                          'False' yields a slightly-more-physical case of
                          atomic diffusion.

        '''
        # Initialization
        # create new instance of ordering array
        ordering = ordering.copy()
        best_ordering = ordering.copy()
        best_energy = self.calc_ce(ordering)
        prev_energy = best_energy
        energy_history = np.zeros(num_steps)
        energy_history[0] = best_energy
        if not swap_any:
            adj_list = [self.bond_list[self.bond_list[:, 0] == i][:, 1].tolist()
                        for i in range(len(self.atoms))]
        for step in range(1, num_steps):
            # Determine where the ones and zeroes are currently
            ones = np.where(ordering == 1)[0]
            zeros = np.where(ordering == 0)[0]

            # Choose a random step
            if swap_any:
                chosen_one = np.random.choice(ones)
                chosen_zero = np.random.choice(zeros)
            else:
                # Search the NP for a 1 with heteroatomic bonds
                for chosen_one in np.random.permutation(ones):
                    connected_atoms = np.array(adj_list[chosen_one])
                    connected_zeros = np.intersect1d(connected_atoms, zeros,
                                                     assume_unique=True)
                    if connected_zeros.size != 0:
                        # The atom has zeros connected to it
                        chosen_zero = np.random.choice(connected_zeros)
                        break

            # Evaluate the energy change
            prev_ordering = ordering.copy()
            ordering[chosen_one] = 0
            ordering[chosen_zero] = 1
            energy = self.calc_ce(ordering)

            # Metropolis-related stuff
            ratio = energy / prev_energy
            if ratio > np.random.uniform():
                # Commit to the step
                energy_history[step] = energy
                if energy < best_energy:
                    best_energy = energy
                    best_ordering = ordering.copy()
            else:
                # Reject the step
                ordering = prev_ordering.copy()
                energy_history[step] = prev_energy

        return best_ordering, best_energy, energy_history
