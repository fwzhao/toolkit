#!/usr/bin/env python

import gzip
import os
import re
import subprocess
import textwrap
import time

from ngs_toolkit import _LOGGER
import numpy as np
import pandas as pd
from pypiper import NGSTk
import requests
from sklearn.preprocessing import MinMaxScaler


def chunks(l, n):
    """
    Partition iterable in `n` chunks.

    :param iterable l: Iterable (e.g. list or numpy array).
    :param int n: Number of chunks to generate.
    """
    n = max(1, n)
    return (l[i:i + n] for i in range(0, len(l), n))


def sorted_nicely(l):
    """
    Sort an iterable in the way that humans expect.

    :param l: Iterable to be sorted
    :type l: iterable
    :returns: Sorted interable
    :rtype: list
    """
    def convert(text): return int(text) if text.isdigit() else text

    def alphanum_key(key): return [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def standard_score(x):
    """
    Compute a standard score, defined as (x - min(x)) / (max(x) - min(x)).

    :param numpy.array x: Numeric array.
    """
    return (x - x.min()) / (x.max() - x.min())


def z_score(x):
    """
    Compute a Z-score, defined as (x - mean(x)) / std(x).

    :param numpy.array x: Numeric array.
    """
    return (x - x.mean()) / x.std()


def count_dataframe_values(x):
    """
    Count number of non-null values in a dataframe.

    :param x: Pandas DataFrame
    :type x: pandas.DataFrame
    :returns: Number of non-null values.
    :rtype: int
    """
    return np.multiply(*x.shape) - x.isnull().sum().sum()


def location_index_to_bed(index):
    bed = pd.DataFrame(index=index)
    index = index.to_series(name='region')
    bed['chrom'] = index.str.split(":").str[0]
    index2 = index.str.split(":").str[1]
    bed['start'] = index2.str.split("-").str[0]
    bed['end'] = index2.str.split("-").str[1]
    return bed


def bed_to_index(df):
    """
    Get an index of the form chrom:start-end
    from a a dataframe with such columns.

    :param pandas.DataFrame df: DataFrame with columns
                                 'chr', 'start' and 'end'.
    """
    cols = ['chrom', 'start', 'end']
    if not all([x in df.columns for x in cols]):
        raise AttributeError("DataFrame does not have '{}' columns."
                             .format("', '".join(cols)))
    index = (
        df['chrom'] +
        ":" +
        df['start'].astype(int).astype(str) +
        "-" +
        df['end'].astype(int).astype(str))
    return pd.Index(index, name="region")


def timedelta_to_years(x):
    """
    Convert a timedelta to years.

    :param x: A timedelta.
    :type x:
    :returns: [description]
    :rtype: {[type]}
    """
    return x / np.timedelta64(60 * 60 * 24 * 365, 's')


def signed_max(x, f=0.66, axis=0):
    """
    Return maximum or minimum of array `x` depending on the sign of the majority of values.
    If there isn't a clear majority (at least `f` fraction in one side), return mean of values.
    If given a pandas DataFrame or 2D numpy array, will apply this across rows (columns-wise, axis=0)
    or across columns (row-wise, axis=1).
    Will return NaN for non-numeric values.

    :param numpy.array x: Numeric array or pandas Dataframe or Series.
    :param float f: Threshold fraction of majority agreement.
    :param int axis: Whether to apply across rows (0, columns-wise) or across columns (1, row-wise).
    :returns: Pandas Series with values reduced to the signed maximum.
    :rtype: pandas.Series
    """
    if axis not in [0, 1]:
        raise ValueError("Axis must be one of 0 (columns) or 1 (rows).")

    if len(x.shape) == 1:
        # Return nan if not numeric
        if x.dtype not in [np.float_, np.int_]:
            return np.nan

        types = [type(i) for i in x]
        if not all(types):
            return np.nan
        else:
            if types[0] not in [np.float_, float, np.int_, int]:
                return np.nan
        ll = float(len(x))
        neg = sum(x < 0)
        pos = sum(x > 0)
        obs_f = max(neg / ll, pos / ll)
        if obs_f >= f:
            if neg > pos:
                return min(x)
            else:
                return max(x)
        else:
            return np.mean(x)
    else:
        if type(x) != pd.DataFrame:
            x = pd.DataFrame(x)

        if axis == 1:
            x = x.T
        res = pd.Series(np.empty(x.shape[1]), index=x.columns)
        for v in x.columns:
            res[v] = signed_max(x.loc[:, v])

        return res


def log_pvalues(x, f=0.1):
    """
    Calculate -log10(p-value) replacing infinite values with:
        ``max(x) + max(x) * f``

    Attributes:

    :param pandas.Series x:
        Series with numeric values

    :returns pandas.Series:
        Transformed values
    """
    ll = (-np.log10(x))
    rmax = ll[ll != np.inf].max()
    return ll.replace(np.inf, rmax + rmax * f)


def r2pandas_df(r_df):
    df = pd.DataFrame(np.asarray(r_df)).T
    df.columns = [str(x) for x in r_df.colnames]
    df.index = [str(x) for x in r_df.rownames]
    return df


# def detect_peaks(x, mph=None, mpd=1, threshold=0, edge='rising',
#                  kpsh=False, valley=False):
#     """Detect peaks in data based on their amplitude and other features.

#     Parameters
#     ----------
#     x : 1D array_like
#         data.
#     mph : {None, number},optional (default = None)
#         detect peaks that are greater than minimum peak height.
#     mpd : positive integer,optional (default = 1)
#         detect peaks that are at least separated by minimum peak distance (in
#         number of data).
#     threshold : positive number,optional (default = 0)
#         detect peaks (valleys) that are greater (smaller) than `threshold`
#         in relation to their immediate neighbors.
#     edge : {None, 'rising', 'falling', 'both'},optional (default = 'rising')
#         for a flat peak, keep only the rising edge ('rising'), only the
#         falling edge ('falling'), both edges ('both'), or don't detect a
#         flat peak (None).
#     kpsh : bool,optional (default = False)
#         keep peaks with same height even if they are closer than `mpd`.
#     valley : bool,optional (default = False)
#         if True (1), detect valleys (local minima) instead of peaks.
#     show : bool,optional (default = False)
#         if True (1), plot data in matplotlib figure.
#     ax : a matplotlib.axes.Axes instance,optional (default = None).

#     Returns
#     -------
#     ind : 1D array_like
#         indeces of the peaks in `x`.

#     Notes
#     -----
#     The detection of valleys instead of peaks is performed internally by simply
#     negating the data: `ind_valleys = detect_peaks(-x)`

#     The function can handle NaN's

#     See this IPython Notebook [1]_.

#     References
#     ----------
#     .. [1] http://nbviewer.ipython.org/github/demotu/BMC/blob/master/notebooks/DetectPeaks.ipynb

#     Examples
#     --------
#     >>> from detect_peaks import detect_peaks
#     >>> x = np.random.randn(100)
#     >>> x[60:81] = np.nan
#     >>> # detect all peaks and plot data
#     >>> ind = detect_peaks(x, show=True)
#     >>> print(ind)

#     >>> x = np.sin(2*np.pi*5*np.linspace(0, 1, 200)) + np.random.randn(200)/5
#     >>> # set minimum peak height = 0 and minimum peak distance = 20
#     >>> detect_peaks(x, mph=0, mpd=20, show=True)

#     >>> x = [0, 1, 0, 2, 0, 3, 0, 2, 0, 1, 0]
#     >>> # set minimum peak distance = 2
#     >>> detect_peaks(x, mpd=2, show=True)

#     >>> x = np.sin(2*np.pi*5*np.linspace(0, 1, 200)) + np.random.randn(200)/5
#     >>> # detection of valleys instead of peaks
#     >>> detect_peaks(x, mph=0, mpd=20, valley=True, show=True)

#     >>> x = [0, 1, 1, 0, 1, 1, 0]
#     >>> # detect both edges
#     >>> detect_peaks(x, edge='both', show=True)

#     >>> x = [-2, 1, -2, 2, 1, 1, 3, 0]
#     >>> # set threshold = 2
#     >>> detect_peaks(x, threshold = 2, show=True)

#     x = np.atleast_1d(x).astype('float64')
#     if x.size < 3:
#         return np.array([], dtype=int)
#     if valley:
#         x = -x
#     # find indices of all peaks
#     dx = x[1:] - x[:-1]
#     # handle NaN's
#     indnan = np.where(np.isnan(x))[0]
#     if indnan.size:
#         x[indnan] = np.inf
#         dx[np.where(np.isnan(dx))[0]] = np.inf
#     ine, ire, ife = np.array([[], [], []], dtype=int)
#     if not edge:
#         ine = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) > 0))[0]
#     else:
#         if edge.lower() in ['rising', 'both']:
#             ire = np.where((np.hstack((dx, 0)) <= 0) & (np.hstack((0, dx)) > 0))[0]
#         if edge.lower() in ['falling', 'both']:
#             ife = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) >= 0))[0]
#     ind = np.unique(np.hstack((ine, ire, ife)))
#     # handle NaN's
#     if ind.size and indnan.size:
#         # NaN's and values close to NaN's cannot be peaks
#         ind = ind[np.in1d(ind, np.unique(np.hstack((indnan, indnan - 1, indnan + 1))), invert=True)]
#     # first and last values of x cannot be peaks
#     if ind.size and ind[0] == 0:
#         ind = ind[1:]
#     if ind.size and ind[-1] == x.size - 1:
#         ind = ind[:-1]
#     # remove peaks < minimum peak height
#     if ind.size and mph is not None:
#         ind = ind[x[ind] >= mph]
#     # remove peaks - neighbors < threshold
#     if ind.size and threshold > 0:
#         dx = np.min(np.vstack([x[ind] - x[ind - 1], x[ind] - x[ind + 1]]), axis=0)
#         ind = np.delete(ind, np.where(dx < threshold)[0])
#     # detect small peaks closer than minimum peak distance
#     if ind.size and mpd > 1:
#         ind = ind[np.argsort(x[ind])][::-1]  # sort ind by peak height
#         idel = np.zeros(ind.size, dtype=bool)
#         for i in range(ind.size):
#             if not idel[i]:
#                 # keep peaks with the same height if kpsh is True
#                 idel = idel | (ind >= ind[i] - mpd) & (ind <= ind[i] + mpd) \
#                     & (x[ind[i]] > x[ind] if kpsh else True)
#                 idel[i] = 0  # Keep current peak
#         # remove the small peaks and sort back the indices by their occurrence
#         ind = np.sort(ind[~idel])

#     return ind


def count_jobs_running(cmd="squeue", sep="\n"):
    """
    Count running jobs on a cluster by invoquing a command that lists the jobs.
    """
    return subprocess.check_output(cmd).split(sep).__len__()


def submit_job_if_possible(cmd, total_job_lim=800, refresh_time=10, in_between_time=5):
    submit = count_jobs_running() < total_job_lim
    while not submit:
        time.sleep(refresh_time)
        submit = count_jobs_running() < total_job_lim
    subprocess.call(cmd.split(" "))
    time.sleep(in_between_time)


def collect_md5_sums(df):
    """
    Given a dataframe with columns with paths to md5sum files ending in '_md5sum',
    replace the paths to the md5sum files with the actual checksums.

    Useful to use in combination with ``project_to_geo``.

    :param pandas.DataFrame df:
        A dataframe with columns ending in '_md5sum'.

    :returns pandas.DataFrame:
        DataFrame with md5sum columns replaced with the actual md5sums.
    """
    cols = df.columns[df.columns.str.endswith("_md5sum")]
    for col in cols:
        for i, path in df.loc[:, col].iteritems():
            if not pd.isnull(path):
                cont = open(path, 'r').read().strip()
                if any([x.isspace() for x in cont]):
                    cont = cont.split(" ")[0]
                df.loc[i, col] = cont
    return df


def sra_id2geo_id(sra_ids):
    """Query SRA ID from GEO ID"""

    cmd = "esearch -db sra -query {}"
    cmd += " | efetch -format docsum"
    cmd += " | xtract -pattern DocumentSummary -element Runs"
    cmd += """ |  perl -ne '@mt = ($_ =~ /SRR\\d+/g); print "@mt"'"""

    geo_ids = list()
    for id in sra_ids:
        geo_ids.append(subprocess.call(cmd.format(id).split(" ")).read())
    return


def sra2fastq(input_sra, output_dir):
    cmd = """
\t\tfastq-dump --split-3 --outdir {} {}
    """.format(output_dir, input_sra)

    return cmd


def fastq2bam(input_fastq, output_bam, sample_name, input_fastq2=None):
    cmd = """
\t\tjava -Xmx4g -jar /cm/shared/apps/picard-tools/1.118/FastqToSam.jar"""
    cmd += " FASTQ={0}".format(input_fastq)
    cmd += " SAMPLE_NAME={0}".format(sample_name)
    if input_fastq2 is not None:
        cmd += " FASTQ2={0}".format(input_fastq2)
    cmd += """ OUTPUT={0}""".format(output_bam)

    return cmd


def decompress_file(file, output_file=None):
    """
    Decompress a gzip-compressed file in chunks (not in memory).
    """
    """
    # test:
    file = "file.bed.gz"
    """
    if output_file is None:
        if not file.endswith(".gz"):
            msg = "`output_file` not given and input_file does not end in '.gz'."
            _LOGGER.error(msg)
            raise ValueError(msg)
        output_file = file.replace(".gz", "")
    with gzip.open(file, 'rb') as _in:
        with open(output_file, 'w') as _out:
            for line in _in.readlines():
                _out.write(line.decode('utf-8'))


def download_file(url, output_file, chunk_size=1024):
    """
    Download a file and write to disk in chunks (not in memory).
    """
    """
    # test:
    url = 'https://egg2.wustl.edu/roadmap/data/byFileType/chromhmmSegmentations'
    url += '/ChmmModels/coreMarks/jointModel/final/E001_15_coreMarks_dense.bed.gz'
    output_file = "file.bed.gz"
    chunk_size = 1024
    """
    response = requests.get(url, stream=True)
    with open(output_file, 'wb') as outfile:
        outfile.writelines(
            response.iter_content(chunk_size=chunk_size))


def download_gzip_file(url, output_file):
    if not output_file.endswith(".gz"):
        output_file += '.gz'
    download_file(url, output_file)
    decompress_file(output_file)
    if (
            os.path.exists(output_file) and
            os.path.exists(output_file.replace(".gz", ""))):
        os.remove(output_file)


def download_cram(link, output_dir):
    cmd = """
    cd {}
    wget '{}'
    cd -
    """.format(output_dir, link)

    return cmd


def cram2bam(input_cram, output_bam):
    cmd = """
    samtools view -b -o {} {}
    """.format(output_bam, input_cram)

    return cmd


def download_sra(link, output_dir):
    cmd = """
    cd {}
    wget '{}'
    cd -
    """.format(output_dir, link)

    return cmd


def sra2bam_job(sra_id, base_path):
    tk = NGSTk()

    # Slurm header
    job_file = os.path.join(base_path, "%s_sra2bam.sh" % sra_id)
    log_file = os.path.join(base_path, "%s_sra2bam.log" % sra_id)

    cmd = tk.slurm_header("-".join(["sra2bam", sra_id]), log_file, cpus_per_task=2)

    # SRA to FASTQ
    cmd += sra2fastq(os.path.join(base_path, sra_id + ".sra"), base_path)

    # FASTQ to BAM
    cmd += fastq2bam(
        os.path.join(base_path, sra_id + "_1.fastq"),
        os.path.join(base_path, sra_id + ".bam"),
        sra_id,
        os.path.join(base_path, sra_id + "_2.fastq"))

    # Slurm footer
    cmd += tk.slurm_footer() + "\n"

    # Write job to file

    with open(job_file, "w") as handle:
        handle.write(textwrap.dedent(cmd))

    # Submit
    tk.slurm_submit_job(job_file)


def link2bam_job(sample_name, link, base_path):
    tk = NGSTk()

    # Slurm header
    job_file = os.path.join(base_path, "%s_link2bam.sh" % sample_name)
    log_file = os.path.join(base_path, "%s_link2bam.log" % sample_name)

    cmd = tk.slurm_header("-".join(["link2bam", sample_name]), log_file, cpus_per_task=2)

    # Download CRAM
    cmd += download_cram(
        link,
        base_path)

    # CRAM to BAM
    cmd += cram2bam(
        os.path.join(base_path, sample_name + ".cram"),
        os.path.join(base_path, sample_name + ".bam"))

    # Slurm footer
    cmd += tk.slurm_footer() + "\n"

    # Write job to file

    with open(job_file, "w") as handle:
        handle.write(textwrap.dedent(cmd))

    # Submit
    tk.slurm_submit_job(job_file)


def sralink2bam_job(sra_id, base_path):
    tk = NGSTk()

    # Slurm header
    job_file = os.path.join(base_path, "%s_sra2bam.sh" % sra_id)
    log_file = os.path.join(base_path, "%s_sra2bam.log" % sra_id)

    cmd = tk.slurm_header("-".join(["sra2bam", sra_id]), log_file, cpus_per_task=2)

    # SRA to FASTQ
    cmd += sra2fastq(sra_id, base_path)

    # FASTQ to BAM
    cmd += fastq2bam(
        os.path.join(base_path, sra_id + "_1.fastq"),
        os.path.join(base_path, sra_id + ".bam"),
        sra_id,
        os.path.join(base_path, sra_id + "_2.fastq"))

    # Slurm footer
    cmd += tk.slurm_footer() + "\n"

    # Write job to file

    with open(job_file, "w") as handle:
        handle.write(textwrap.dedent(cmd))

    # Submit
    tk.slurm_submit_job(job_file)
    _LOGGER.info(job_file)


def series_matrix2csv(matrix_url, prefix=None):
    """
    matrix_url: gziped URL with GEO series matrix.
    """

    subprocess.call("wget {}".format(matrix_url).split(" "))
    filename = matrix_url.split("/")[-1]

    with gzip.open(filename, 'rb') as f:
        file_content = f.read()

    # separate lines with only one field (project-related)
    # from lines with >2 fields (sample-related)
    prj_lines = dict()
    sample_lines = dict()

    for line in file_content.decode("utf-8").strip().split("\n"):
        line = line.strip().split("\t")
        if len(line) == 2:
            prj_lines[line[0].replace("\"", "")] = line[1].replace("\"", "")
        elif len(line) > 2:
            sample_lines[line[0].replace("\"", "")] = [x.replace("\"", "") for x in line[1:]]

    prj = pd.Series(prj_lines)
    prj.index = prj.index.str.replace("!Series_", "")

    samples = pd.DataFrame(sample_lines)
    samples.columns = samples.columns.str.replace("!Sample_", "")

    if prefix is not None:
        prj.to_csv(os.path.join(prefix + ".project_annotation.csv"), index=True)
        samples.to_csv(os.path.join(prefix + ".sample_annotation.csv"), index=False)

    return prj, samples


def deseq_results_to_bed_file(
        deseq_result_file, bed_file, sort=True, ascending=False, normalize=False,
        significant_only=False, alpha=0.05, abs_fold_change=1.):
    """
    Write BED file with fold changes from DESeq2 as score value.
    """
    df = pd.read_csv(deseq_result_file, index_col=0)

    msg = "DESeq2 results do not have a 'log2FoldChange' column."
    if not ("log2FoldChange" in df.columns.tolist()):
        _LOGGER.error(msg)
        raise AssertionError(msg)

    if sort is True:
        df = df.sort_values("log2FoldChange", ascending=ascending)

    if significant_only is True:
        df = df.loc[(df['padj'] < alpha) & (df['log2FoldChange'].abs() > abs_fold_change), :]

    # decompose index string (chrom:start-end) into columns
    df['chrom'] = map(lambda x: x[0], df.index.str.split(":"))
    r = pd.Series(map(lambda x: x[1], df.index.str.split(":")))
    df['start'] = map(lambda x: x[0], r.str.split("-"))
    df['end'] = map(lambda x: x[1], r.str.split("-"))
    df['name'] = df.index
    if normalize:
        MinMaxScaler(feature_range=(0, 1000)).fit_transform(df["log2FoldChange"])
    df['score'] = df["log2FoldChange"]

    df[["chrom", "start", "end", "name", "score"]].to_csv(bed_file, sep="\t", header=False, index=False)
