import sqlalchemy as db
import numpy as np
import pickle
import os
import datetime

try:
    import db_utils
    import base
    import datatables as tbl
except:
    from npdb import db_utils
    import npdb.base as base
    import npdb.datatables as tbl
import pandas as pd
import matplotlib
import matplotlib.ticker
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sys
from ase.data.colors import jmol_colors
from ase.data import chemical_symbols
sys.path.append('..')
import plot_defaults

"""
    Functions to interface with NP GA Database
    - all methods follow a specific prefix form

    Function Types:
       get_: retrieves data from DB
             - does NOT edit DB entries
             - NOTE: returns Datatable objects

     build_: uses data from DB to build desired object(s)
             - does NOT edit DB entries
             - NOTE: returns data in other forms besides Datatable objects
                     - e.g. pd.DataFrame, plt.Figure, np.array, etc.

    insert_: adds new data to DB
             - does NOT edit current DB entries
             - adds new rows to DB

    update_: updates data in existing entries
             - does edit current DB entries
             - if no current entry matches criteria, a new
               entry will be made if allow_entry=True

    remove_: removes an entry/entries from DB
             - does edit current DB entries
"""

# global session
session = base.Session(autoflush=True)

# create all datatables if not present in DB
base.Base.metadata.create_all(base.engine)


# BUILD FUNCTIONS


def build_df(datatable, lim=None, custom_filter=None, **kwargs):
    """
    GENERIC FUNCTION
    Returns pandas dataframe of entries in <datatable>
    that match criteria in <**kwargs>
    - NOTE: changes 'shape' column name to 'np_shape'!

    Args:
    - datatable (Datatable class): datatable to query

    KArgs:
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - **kwargs: arguments whose name(s) matches a column in the datatable

    Returns:
    - (pd.DataFrame): df of results
    """

    # convert sql query results into pd.DataFrame
    qry = get_entry(datatable, lim=lim, custom_filter=custom_filter,
                    **kwargs, return_query=True).statement
    df = pd.read_sql(qry, session.bind)
    df.columns = [col if col != 'shape' else 'np_shape' for col in df.columns]
    return df


def build_atoms_in_shell_list(shape, shell):
    """
    Returns:
    (list): atom indices that are in <shell> selected
    """
    has_center = {'cuboctahedron': False,
                  'fcc-cube': False,
                  'icosahedron': True,
                  'elongated-pentagonal-bipyramid': True}

    assert shell != 0 and shell < 15
    # get positions of all shells < <shell>
    oneless = get_nanoparticle(shape, num_shells=shell - 1, lim=1)
    if oneless:
        rem_atoms = oneless.get_atoms_obj_skel().positions
    else:
        rem_atoms = []
        # rem_atoms = np.zeros((2, 3)) if has_center[shape] else np.zeros(3)

    # get positions of all shells <= <shell>
    actual = get_nanoparticle(shape, num_shells=shell, lim=1)
    if not actual:
        return [0] if has_center[shape] else []
    keep_atoms = actual.get_atoms_obj_skel().positions

    if len(rem_atoms) == 0:
        return range(len(keep_atoms))

    # center atoms
    rem_atoms = (rem_atoms - rem_atoms.mean(0)).round(3)

    keep_atoms = (keep_atoms - keep_atoms.mean(0)).round(3)

    if not (isinstance(rem_atoms, np.ndarray) and
            isinstance(keep_atoms, np.ndarray)):
        raise ValueError("Unable to find shells")

    rem_atoms = rem_atoms.tolist()
    keep_atoms = keep_atoms.tolist()

    return [i for i in range(len(keep_atoms))
            if keep_atoms[i] not in rem_atoms]


def build_shell_dist_fig(bimet, show=False):
    """
    Creates shell distribution figure of
    BimetallicResult

    Args:

    Returns:
    (plt.Figure)
    """
    atoms = bimet.build_atoms_obj().copy()

    # center atoms at origin (COP)
    atoms.positions -= atoms.positions.mean(0)

    shell_ls = []
    tot_count = []
    m1_count = []
    m2_count = []

    for shell in range(1, bimet.nanoparticle.num_shells + 1):
        inshell = atoms[build_atoms_in_shell_list(bimet.shape, shell)]
        if len(inshell) == 0:
            continue

        shell_ls.append(shell)
        tot_count.append(len(inshell))
        m1_count.append(len([i for i in inshell if i.symbol == bimet.metal1]))
        m2_count.append(len([i for i in inshell if i.symbol == bimet.metal2]))

    tot_count = np.array(tot_count)
    m1_count = np.array(m1_count)
    m2_count = np.array(m2_count)

    # normalize counts to concentrations
    norm_m1 = m1_count / tot_count
    norm_m2 = m2_count / tot_count

    fig, axes = plt.subplots(2, 1, sharex=True)
    ax1, ax2 = axes

    m1_color = jmol_colors[chemical_symbols.index(bimet.metal1)]
    m2_color = jmol_colors[chemical_symbols.index(bimet.metal2)]

    ax1.plot(shell_ls, m1_count, 'o-', markeredgecolor='k',
             color=m1_color, markersize=8, label=bimet.metal1)
    ax1.plot(shell_ls, m2_count, 'o-', markeredgecolor='k',
             color=m2_color, markersize=8, label=bimet.metal2)
    ax1.legend(loc='upper left')
    ax1.set_xticks(list(range(1, bimet.nanoparticle.num_shells + 1)))

    # set ylim to maximum number of atoms on surface
    high = int(round((tot_count[-1] + 10) * 10) / 10)
    ax1.set_ylim(0, high)
    # ax1.set_yticks(range(0, high + 1, 10))
    ax1.set_ylabel('# of Atoms')

    ax2.plot(shell_ls, norm_m1, 'o-', markeredgecolor='k',
             color=m1_color, markersize=8)
    ax2.plot(shell_ls, norm_m2, 'o-', markeredgecolor='k',
             color=m2_color, markersize=8)
    ax2.set_ylabel('Concentration')
    ax2.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax2.set_yticklabels(['{:,.0%}'.format(x) for x in ax2.get_yticks()])
    ax2.set_xticks(list(range(1, bimet.nanoparticle.num_shells + 1)))
    ax2.set_xticklabels(['Core'] +
                        ['Shell %i' % i
                         for i in range(2, bimet.nanoparticle.num_shells)] +
                        ['Surface'], rotation=45)

    fig.suptitle(bimet.build_chem_formula().replace('\\rm', '\\rm \\bf') + ' - %s' % shape)
    fig.tight_layout(rect=(0, 0, 1, 0.9))

    if show:
        fig.show()
    return fig


def build_coefficient_dict(metals):
    """
    Creates coefficient dictionary used to calc CE

    Args:
    - metals (string || iterable): string(s) containing two metal elements

    Returns:
    - (dict): coefficient dictionary for GA sim
    """
    metal1, metal2 = db_utils.sort_metals(metals)

    # homoatomic half bond energies
    res_aa = get_model_coefficient(metal1, metal1)
    res_bb = get_model_coefficient(metal2, metal2)

    # heteroatomic half bond energies
    res_ab = get_model_coefficient(metal1, metal2)
    res_ba = get_model_coefficient(metal2, metal1)

    # raise error if coefficients are not found
    errors = []
    for res, ms in zip([res_aa, res_bb, res_ab, res_bb],
                       ((metal1, metal1), (metal2, metal2),
                        (metal1, metal2), (metal2, metal1))):
        if not res:
            errors.append("no info for %s - %s coefficients" % ms)
    if errors:
        raise db_utils.NPDatabaseError('\n'.join(errors))

    # return back coefficients as dictionary of dictionaries
    return {metal1: {metal1: list(map(lambda i: i.bond_energy, res_aa)),
                     metal2: list(map(lambda i: i.bond_energy, res_ab))},
            metal2: {metal2: list(map(lambda j: j.bond_energy, res_bb)),
                     metal1: list(map(lambda j: j.bond_energy, res_ba))}}


def build_metals_list():
    """
    Returns list of possible metal combinations for GA sims
    """
    return [r[0] for r in session.query(tbl.ModelCoefficients.element1)
            .distinct().order_by(tbl.ModelCoefficients.element1).all()]


def build_new_structs_plot(metal_opts, shape_opts, pct=False,
                           cutoff_date=None):
    """
    Uses BimetallicLog to create 2D line plot of
    new structures found vs. datetime

    Args:
    - metal_opts (list): list of metal options
    - shape_opts (list): list of shape options

    Kargs:
    - pct (bool): if True, y-axis = % new structures
                  else, y-axis = number of new structures
    - cutoff_date (Datetime.Datetime): if given, will filter out runs
                                       older than <cutoff_date>

    Returns:
    - (plt.Figure): 2D line plot object
    """
    if isinstance(metal_opts, str):
        metal_opts = [metal_opts]
    if isinstance(shape_opts, str):
        shape_opts = [shape_opts]

    # if cutoff_date, create custom_filter
    if isinstance(cutoff_date, datetime.datetime):
        custom_filter = tbl.BimetallicLog.date >= cutoff_date
    else:
        custom_filter = None

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    fig, ax = plt.subplots()
    i = 0
    tot_lines = len(metal_opts) * len(shape_opts)
    for j, m in enumerate(metal_opts):
        metal1, metal2 = db_utils.sort_metals(m)
        for point, shape in zip(['o', 'x', '^', 's'], shape_opts):
            # use abbreviated names for shapes
            lbl_shape = shape \
                .replace('icosahedron', 'Ico') \
                .replace('cuboctahedron', 'Cuboct') \
                .replace('fcc-cube', 'FCC-Cube') \
                .replace('elongated-pentagonal-bipyramid', 'J16')

            # pd.DataFrame of bimetallic log data
            df = build_df(tbl.BimetallicLog, metals=m, shape=shape,
                          custom_filter=custom_filter)
            x = df.date.values
            label = '%s%s: %s' % (metal1, metal2, lbl_shape)
            # color = plt.cm.tab20c((i / float(tot_lines)) * 0.62)

            y = df.new_min_structs.values
            if pct:
                y = y / df.tot_structs.values[0]

            ax.plot(x, y, '%s-' % point, label=label,
                    color=colors[j])
            i += 1

    if pct:
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter('{0:.0%}'.format))
        ax.set_ylim(0, 1)
        ax.set_ylabel('Percent Count')
    else:
        ax.set_ylabel('Total Count')
    ax.legend(ncol=len(metal_opts))
    ax.set_title('New Minimum Structures Found')
    ax.set_xlabel('Batch Run Date')

    # (month/day) x axis tick labels
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d'))
    fig.tight_layout()
    return fig


def build_prdf_shapes_comparison(metals, num_shells, x_dope):
    """
    Creates list of figures, each containing partial radial distribution
        functions (PRDFs) of a given shape

    Args:
    - metals (str || iterable): two metal elements
    - num_shells (int): number of shells (i.e. layers) of atoms used to make NP
    - x_dope (float): percentage of metal2 in NPs

    Returns:
    - list of plt.Figure elements containing PRDFs and an image of the NPs
    """
    x_metal1 = 1 - x_dope
    figs = []
    for shape in build_shapes_list():
        num_atoms = get_shell2num(shape, num_shells)
        n_metal1 = num_atoms - int(x_metal1 * num_atoms)
        bi = get_bimet_result(metals=metals,
                              shape=shape,
                              num_atoms=num_atoms,
                              n_metal1=n_metal1)

        figs.append(bi.build_prdf_plot())
    return figs


def build_shell2num_dict(shape=None):
    """
    Builds a number of shells --> number of atoms dict

    Kargs:
    - shape (str): shape of NP

    Returns:
    - dict: shell2num_dict[shape][num_shell] = num_atoms
    """

    nanops = get_nanoparticle(shape=shape)
    result = {}
    for nanop in nanops:
        if nanop.shape not in result:
            result[nanop.shape] = {nanop.num_shells: nanop.num_atoms}
        else:
            result[nanop.shape][nanop.num_shells] = nanop.num_atoms
    return result


def build_srf_plot(metals, shape, T=None):
    """
    Creates a 3D surface plot from NP SQL database
    - plots Size vs. Shape vs. Excess Energy (EE)
    - can also use configurational entropy of mixing
      to plot Size vs. Shape vs. G = EE - T * delS(mix)

    Args:
    - metals (string || iterable): string(s) containing two metal elements
    - shape (string): shape of the NP

    KArgs:
    T (float): if temperature is given, plot G(mix)
               (i.e. include configurational entropy)
               (Default: None)

    Returns:
    - (plt.figure): figure of 3D surface plot
    """
    metal1, metal2 = db_utils.sort_metals(metals)

    runs = session.query(tbl.BimetallicResults.diameter,
                         (tbl.BimetallicResults.n_metal2 /
                          db.cast(tbl.BimetallicResults.num_atoms,
                                  db.Float))
                         .label('comps'),
                         tbl.BimetallicResults.EE) \
        .filter(db.and_(tbl.BimetallicResults.metal1 == metal1,
                        tbl.BimetallicResults.metal2 == metal2,
                        tbl.BimetallicResults.shape == shape)) \
        .statement
    df = pd.read_sql(runs, session.bind)

    # three parameters to plot
    size = df.diameter.values
    comps = df.comps.values
    ees = df.EE.values

    if T is not None:
        # k_b T [eV] = (25.7 mEV at 298 K)
        kt = 25.7E-3 * (T / 298.)
        del_s = comps * np.ma.log(comps).filled(0) + \
            (1 - comps) * np.ma.log(1 - comps).filled(0)
        del_s *= -kt

        ees -= del_s

    # plots surface as heat map with warmer colors for larger EEs
    colormap = plt.get_cmap('coolwarm')
    normalize = matplotlib.colors.Normalize(vmin=ees.min(), vmax=ees.max())

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    try:
        ax.plot_trisurf(comps, size, ees,
                        cmap=colormap, norm=normalize)
    except RuntimeError:
        # if not enough data to create surface, make a scatter plot instead
        ax.scatter3D(comps, size, ees,
                     cmap=colormap, norm=normalize)
    ax.set_xlabel('$X_{%s}$' % metal2)
    ax.set_ylabel('Size (nm)')
    if delg:
        ax.set_zlabel('G (eV)')
        ax.set_title('%iK\n%s %s %s' % (T, metal1, metal2, shape.title()))
    else:
        ax.set_zlabel('EE (eV)')
        ax.set_title('%s %s %s' % (metal1, metal2, shape.title()))
    return fig


def build_radial_distributions(metals=None, shape=None, num_atoms=None,
                            n_metal1=None, lim=None, nbins = "Auto"):
    """
    Sends a query to get_bimetallic_results to construct a list of NPs,
    then for each NP found, returns radial distribution functions for the
    two elements.

    Args:
    metals (str || iterable): two metal elements
    shape (str): shape of NP
    num_atoms (int): number of atoms in NP
    n_metal1 (int): number of metal1 atoms in NP
    lim (int): max number of entries returned
               (default: None = no limit)
    bins (int || str) : Number of bins to use for the radial distribution.
                If set to "Auto", uses num_atoms / 10, rounded up

    Returns:
        A list of N radial distribution functions as dicts. First element gives the
        atom type. Second element gives the dimension. Third element is the value at
        that dimension. For example, returned_value["Cu"]["distance"][3] equaling 3.4
        indicates that whatever returned_value["Cu"]["density"][3] equals is at distance 3.4
    """
    # Do the query
    query = get_bimet_result(metals, shape, num_atoms, n_metal1, lim, return_query=False)
    if type(query) is not list:
        query = [query]
    for system in query:
        element1 = system.metal1
        element2 = system.metal2
        radius = system.diameter / 2
        np = system.nanoparticle
        atoms = np.atoms_obj

        # Todo: Figure out why atoms is an ase.Atoms object in console, but is NoneType when running the script
        import ase
        assert type(atoms) == ase.Atoms
        center = np.mean(atoms.positions, axis=0)

        element_1_distances = []
        element_2_distances = []

        for atom in atoms:
            if atom.symbol == element1:
                element_1_distances.append(np.linalg.norm(atom.position - center))
            elif atom.symbol == element2:
                element_2_distances.append(np.linalg.normm(atom.position - center))

        if nbins == "Auto":
            nbins = int(np.ceil(len(atoms) / 10))

        bins = np.linspace(0, radius, nbins)

        element_1_histogram = np.histogram(element_1_distances, bins)
        element_2_histogram = np.histogram(element_2_distances, bins)

        return zip(bins, element_1_histogram, element_2_histogram)


def build_shapes_list():
    """
    Returns all shapes found in Nanoparticles Datatable as list of str
    """
    return sorted([i[0] for i in session.query(tbl.Nanoparticles.shape)
                   .distinct().all()])


# GET FUNCTIONS


def get_entry(datatable, lim=None, custom_filter=None,
              return_query=False, **kwargs):
    """
    GENERIC FUNCTION
    Returns entry/entries from table if criteria is matched
    - if no criteria given, all data (up to <lim> amount)
      returned

    Args:
    - datatable (Datatable class): datatable to query

    Kargs:
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - custom_filter (sqlalchemy.sql.elements.BinaryExpression):
                    custom sqlalchemy filter that will be applied
                    (default: None = no added filter)
    - return_query (bool): if True, return query and
                           not results
    - **kwargs: arguments whose name(s) matches a column in the datatable

    Returns:
    - (Datatable instance(s)) if match is found else (None)
    """
    match_ls = []
    for attr in kwargs:
        if kwargs[attr] is not None:
            if attr == 'metals':
                metal1, metal2 = db_utils.sort_metals(kwargs[attr])
                match_ls.append(datatable.metal1 == metal1)
                match_ls.append(datatable.metal2 == metal2)
            else:
                match_ls.append(getattr(datatable, attr) == kwargs[attr])

    if type(custom_filter) != type(None):
        match_ls.append(custom_filter)
    match = db.and_(*match_ls)
    qry = session.query(datatable).filter(match).limit(lim)
    if return_query:
        return qry
    res = qry.all()
    return res if len(res) != 1 else res[0]


def get_bimet_log(metals=None, shape=None, date=None, lim=None,
                  return_query=False):
    """
    Returns BimetallicLog entry that matches criteria
    - if no criteria given, all data (up to <lim> amount)
      returned

    Kargs:
    - metals (str || iterable): two metal elements
    - shape (str): shape of NP
    - date (datetime.datetime): GA batch run completion time
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - return_query (bool): if True, return query and
                           not results

    Returns:
    - (BimetallicResults)(s) if match is found else (None)
    """
    return get_entry(tbl.BimetallicLog, **locals())


def get_bimet_result(metals=None, shape=None, num_atoms=None, num_shells=None,
                     n_metal1=None, only_bimet=False,
                     lim=None, return_query=False, custom_filter=None):
    """
    Returns BimetallicResults entry that matches criteria
    - if no criteria given, all data (up to <lim> amount)
      returned

    Kargs:
    - metals (str || iterable): two metal elements
    - shape (str): shape of NP
    - num_atoms (int): number of atoms in NP
    - n_metal1 (int): number of metal1 atoms in NP
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - return_query (bool): if True, return query and
                           not results

    Returns:
    - (BimetallicResults)(s) if match is found else (None)
    """
    if not num_atoms and (num_shells and shape):
        num_atoms = get_shell2num(shape, num_shells)

    if only_bimet:
        only_bimet = db.and_(tbl.BimetallicResults.n_metal1 != 0,
                             tbl.BimetallicResults.n_metal2 != 0)
        custom_filter = only_bimet

    return get_entry(tbl.BimetallicResults, metals=metals, shape=shape,
                     num_atoms=num_atoms, n_metal1=n_metal1, lim=lim,
                     return_query=return_query, custom_filter=custom_filter)


def get_model_coefficient(element1=None, element2=None, cn=None,
                          lim=None, return_query=False):
    """
    Returns tbl.ModelCoefficients entries that match criteria
    - if no criteria given, all data (up to <lim> amount)
      returned
    - query is always ordered by cn

    Kargs:
    - element1 (str): first element
    - element2 (str): second element
    - cn (int): coordination number of element 1
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - return_query (bool): if True, returns just the query
                           and not the results

    Returns:
    - (tbl.ModelCoefficients)(s) if match else (None)
    """
    return get_entry(tbl.ModelCoefficients, **locals())


def get_nanoparticle(shape=None, num_atoms=None, num_shells=None,
                     lim=None, return_query=False):
    """
    Returns tbl.Nanoparticles entries that match criteria
    - if no criteria given, all data (up to <lim> amount)
      returned

    Kargs:
    - shape (str): shape of NP
    - num_atoms (int): number of atoms in NP
    - num_shells (int): number of shells used to build NP
                        from structure_gen module
    - lim (int): max number of entries returned
                 (default: None = no limit)
    - return_query (bool): if True, returns just the query
                           and not the results

    Returns:
    - (tbl.Nanoparticles)(s) if match else (None)
    """
    return get_entry(tbl.Nanoparticles, **locals())


def get_shell2num(shape, num_shells):
    """
    Returns the number of atoms of an NP
    given shape and number of shells

    Args:
    - shape (str): shape of NP
    - num_shells (int): number of shells used to build NP
                        from structure_gen module
    """
    nanop = get_nanoparticle(shape=shape, num_shells=num_shells)
    if nanop:
        return nanop.num_atoms
    else:
        return False


# INSERT FUNCTIONS


def insert_model_coefficients(coeffs_dict=None):
    """
    Inserts model coefficients into ModelCoefficients
    - checks DB to ensure entry does not already exist

    Kargs:
    - coeffs_dict (dict): dictionary of coefficients
                          if None, read in from data directory
                          (default: None)

    Returns:
    - (bool): True if successful insertion else False
    """
    if not coeffs_dict:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', '..', 'data', 'coefs_set.pickle')
        with open(path, 'rb') as fid:
            coeffs_dict = pickle.load(fid)

    # dict(element1=dict(element2=[bond_energies where index = cn]))
    for e1 in coeffs_dict:
        for e2 in coeffs_dict[e1]:
            for cn in range(len(coeffs_dict[e1][e2])):
                if not get_model_coefficient(e1, e2, cn, lim=1):
                    session.add(tbl.ModelCoefficients(e1, e2, cn,
                                                      coeffs_dict[e1][e2][cn]))
    return db_utils.commit_changes(session)


def insert_nanoparticle(atom, shape, num_shells=None):
    """
    Inserts NP and their appropriate atoms into DB

    Args:
    - atom (ase.Atoms): atoms object of NP skeleton
    - shape (string): common name for shape of NP
                      - e.g. icosahedron
                      - always lower case

    Kargs:
    - num_shells (int): number of shells used to build NP
                        from structure_gen module

    Returns:
    - (Nanoparticle): tbl.Nanoparticles object
    """
    np = tbl.Nanoparticles(shape.lower(), len(atom), num_shells=num_shells)
    session.add(np)
    for i, a in enumerate(atom):
        session.add(tbl.Atoms(i, a.x, a.y, a.z, np))
    res = db_utils.commit_changes(session, raise_exception=True)
    return np


def insert_bimetallic_log(start_time, metal1, metal2, shape,
                          ga_generations, shell_range, new_min_structs,
                          tot_structs, batch_run_num=None):
    """
    """
    session.add(tbl.BimetallicLog(start_time, metal1, metal2, shape,
                                  ga_generations, shell_range, new_min_structs,
                                  tot_structs, batch_run_num))
    return db_utils.commit_changes(session)


# UPDATE FUNCTIONS


def update_entry(entry_inst):
    """
    GENERIC METHOD
    Updates datarow object

    Args:
    - entry_inst (DataTable): DataTable object where changes have been made

    Returns:
    - (bool): True if successful
    """
    session.add(entry_inst)
    return db_utils.commit_changes(session)


def update_bimet_result(metals, shape, num_atoms,
                        diameter, n_metal1,
                        CE, ordering, EE=None, nanop=None,
                        allow_insert=True, ensure_ce_min=True):
    """
    Takes raw data and inserts the BimetallicResults datatable
    - will update CE, EE, and ordering of an entry if necessary

    Returns:
    - BimetallicResults entry after successfully updating
    """
    res = get_bimet_result(metals=metals,
                           shape=shape,
                           num_atoms=num_atoms,
                           n_metal1=n_metal1)
    if res:
        # if ensure_ce_min, do not overwrite a minimum CE structure
        # with new data
        if ensure_ce_min and res.CE < CE:
            return
        res.CE = CE
        res.ordering = ordering
        res.EE = EE
    elif not allow_insert:
        return
    else:
        metal1, metal2 = db_utils.sort_metals(metals)
        res = tbl.BimetallicResults(
            metal1=metal1,
            metal2=metal2,
            shape=shape,
            num_atoms=num_atoms,
            diameter=diameter,
            n_metal1=n_metal1,
            n_metal2=num_atoms - n_metal1,
            CE=CE,
            ordering=ordering,
            EE=EE)
        if nanop:
            nanop.bimetallic_results.append(res)
            session.add(nanop)

    # commit changes
    session.add(res)
    db_utils.commit_changes(session, raise_exception=True)
    return res


# REMOVE FUNCTIONS
def remove_entry(entry_inst):
    """
    GENERIC FUNCTION
    Deletes entry (and its children if applicable) from DB

    Args:
    - entry_inst (DataTable instance): datarow to be deleted
    """
    session.delete(entry_inst)
    return db_utils.commit_changes(session)


def remove_nanoparticle(shape=None, num_atoms=None, num_shells=None):
    """
    Removes a single NP and its corresponding atoms
    - only commits if a single np is queried to be removed

    Kargs:
    - shape (str): shape of NP
    - num_atoms (int): number of atoms in NP
    - num_shells (int): number of shells used to build NP
                        from structure_gen module

    Returns:
    - True if successful
    """
    res = get_nanoparticle(shape, num_atoms, num_shells)
    if isinstance(res, list):
        raise db_utils.NPDatabaseError('Can only remove one Nanoparticle')
    elif not res:
        raise db_utils.NPDatabaseError('Unable to find matching Nanoparticle')
    else:
        return remove_entry(res)


def gen_coeffs_dict_from_raw(metal1, metal2, bulkce_m1, bulkce_m2,
                             homo_bde_m1, homo_bde_m2, hetero_bde, cnmax=12):
    """
        Generates the Bond-Centric half bond energy terms for a bimetallic
        pair AB. Coordination number 0 is given the value None. Dictionary is
        used with AtomGraph to calculate total CE of bimetallic nanoparticles.
        Relies on raw data arguments to create dictionary.

        Args:
        - metal1 (str): atomic symbol of metal 1
        - metal2 (str): atomic symbol of metal 2
        - bulkce_m1 (float): bulk cohesive energy (in eV / atom) of metal1
        - bulkce_m2 (float): bulk cohesive energy (in eV / atom) of metal2
        - homo_bde_m1 (float): m1-m1 (homoatomic) bond dissociation energy
        - homo_bde_m2 (float): m2-m2 (homoatomic) bond dissociation energy
        - hetero_bde (float): m1-m2 (heteroatomic) bond dissociation energy

        KArgs:
        - cnmax: maximum bulk coordination number (CN) of metals
                 (Default: 12)

        Returns:
        - (dict): form dict[m1][m2][CN] = half bond energy term
    """
    metals = [metal1, metal2]

    # calculate gammas
    gamma_m1 = (2 * (hetero_bde - homo_bde_m2)) / (homo_bde_m1 - homo_bde_m2)
    gamma_m2 = 2 - gamma_m1

    # create bulkce and gamma dictionaries
    bulkce = {metal1: bulkce_m1,
              metal2: bulkce_m2}
    gammas = {metal1: {metal1: 1, metal2: gamma_m1},
              metal2: {metal2: 1, metal1: gamma_m2}}

    # calculate "total gamma" params (part of BC model that is independent of
    # current atomic CN)
    totgamma = {}
    for m in metals:
        totgamma[m] = {}
        for m2 in metals:
            totgamma[m][m2] = gammas[m][m2] * bulkce[m] / np.sqrt(cnmax)

    # create coefficient dictionary
    coeffs = {}
    for m in metals:
        coeffs[m] = {}
        for m2 in metals:
            coeffs[m][m2] = [None if cn == 0 else totgamma[m][m2] / np.sqrt(cn)
                             for cn in range(cnmax + 1)]
    return coeffs


if __name__ == '__main__':
    cnmax = 12
    metal1 = 'Fe'
    metal2 = 'Pt'
    bulkce_m1 = -4.28
    bulkce_m2 = -5.84

    homo_bde_m1 = 100
    homo_bde_m2 = 278
    hetero_bde = 206

    coeffs = gen_coeffs_dict_from_raw(metal1=metal1, metal2=metal2,
                                      bulkce_m1=bulkce_m1, bulkce_m2=bulkce_m2,
                                      homo_bde_m1=homo_bde_m1,
                                      homo_bde_m2=homo_bde_m2,
                                      hetero_bde=hetero_bde)
    # insert_model_coefficients(coeffs)
    sys.exit()

    # get all bimetallic NPs of given metals and shape
    metals = 'aucu'
    shape = 'icosahedron'
    # num_shells = 8
    # x_dope = 0.7

    """
    import pathlib
    path = os.path.join(os.path.expanduser('~'),
                        'Box Sync', 'Michael_Cowan_PhD_research',
                        'data', 'np_ce', 'shell_dist_plots')

    for metals in ['aucu', 'agcu', 'agau']:
        print(metals.center(40, '-'))

        pathlib.Path(os.path.join(path, metals)).mkdir(exist_ok=True)

        for shape in ['icosahedron', 'cuboctahedron', 'fcc-cube',
                      'elongated-pentagonal-bipyramid']:
            print(shape.center(40))

            pathlib.Path(os.path.join(path, metals, shape)).mkdir(
                exist_ok=True)

            for num_shells in range(2, 11):
                pathlib.Path(os.path.join(path, metals, shape,
                                          str(num_shells))).mkdir(
                                              exist_ok=True)

                results = get_bimet_result(metals, shape,
                                           num_shells=num_shells)
                print(str(num_shells).center(40))
                for i, r in enumerate(results):
                    f = build_shell_dist_fig(r)
                    form = r.build_chem_formula(False)
                    f.savefig(
                        os.path.join(path, metals, shape, str(num_shells),
                                     '%02i_%s.png' % (i, form)),
                        dpi=300)
                    plt.close('all')
            print()
        print()
    sys.exit()

    cutoff = datetime.datetime(2019, 4, 23)
    # f = build_new_structs_plot(['agau', 'aucu', 'agcu'],
    #                           ['cuboctahedron', 'icosahedron', 'fcc-cube'],
    #                           pct=False, cutoff_date=cutoff)

    figs = build_prdf_shapes_comparison(metals, num_shells, x_dope)
    # figs[2].savefig('C:/users/yla/desktop/test.svg')
    plt.show()
    # f = build_new_structs_plot(metals, shape, True)
    # only bimetallic NPs
    only_bimet = db.and_(tbl.BimetallicResults.n_metal1 != 0,
                         tbl.BimetallicResults.n_metal2 != 0)

    nanops = get_bimet_result(metals=metals, shape=shape, return_query=True) \
        .filter(only_bimet).all()

    bimets = get_bimet_result(metals, shape=shape, num_shells=num_shells,
                              only_bimet=True)[-3:]
    res = []
    for bi in bimets:
        res.append(bi.build_prdf_plot())
    plt.show()

    # Test histogram
    # print(build_radial_distributions(metals="CuAg", shape="icosahedron",
    #                                  num_atoms=55, lim=12))
    """
