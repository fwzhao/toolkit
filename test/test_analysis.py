#!/usr/bin/env python


import os
import pytest
from .data_generator import generate_project
from ngs_toolkit.analysis import Analysis
from ngs_toolkit.atacseq import ATACSeqAnalysis


@pytest.fixture
def analysis(tmp_path):
    import yaml
    from peppy import Project
    tmp_path = str(tmp_path)  # for Python2

    # Let's make several "reallish" test projects
    project_prefix_name = "test-project"
    data_type = "ATAC-seq"
    organism, genome_assembly = ("human", "hg38")

    n_factors = [1, 2, 3][0]
    n_variables = [100, 1000, 10000][0]
    n_replicates = [1, 2, 5][0]
    project_name = "{}_{}_{}_{}_{}_{}".format(
        project_prefix_name, data_type, genome_assembly,
        n_factors, n_variables, n_replicates)

    generate_project(
        output_dir=tmp_path,
        project_name=project_name,
        organism=organism, genome_assembly=genome_assembly,
        data_type=data_type,
        n_factors=n_factors, n_replicates=n_replicates, n_variables=n_variables)

    # first edit the defaul path to the annotation sheet
    config = os.path.join(
        tmp_path, project_name, "metadata", "project_config.yaml")
    c = yaml.safe_load(open(config, 'r'))
    c['metadata']['sample_annotation'] = os.path.abspath(
        os.path.join(tmp_path, project_name, "metadata", "annotation.csv"))
    c['metadata']['comparison_table'] = os.path.abspath(
        os.path.join(tmp_path, project_name, "metadata", "comparison_table.csv"))
    yaml.safe_dump(c, open(config, "w"))

    prj_path = os.path.join(tmp_path, project_name)
    os.chdir(prj_path)

    # project and associated analysis
    analysis = ATACSeqAnalysis(
        name=project_name,
        prj=Project(config),
        results_dir=os.path.join(prj_path, "results"))
    analysis.load_data()

    return analysis


class Test_Analysis():
    def test_analysis_creation(self, tmp_path):
        import os
        from peppy import Project
        import yaml
        import shutil

        tmp_path = str(tmp_path)  # for Python2

        name = "test_analysis"

        a = Analysis(name=name)
        assert a.__repr__() == "Analysis '{}'.".format(name)
        assert "samples" not in a.__repr__()

        # Let's make several "reallish" test projects
        project_prefix_name = "test-project"
        data_types = ["ATAC-seq", "RNA-seq", "ChIP-seq"]  # "CNV"
        genome_assemblies = [("human", "hg19"), ("human", "hg38"), ("mouse", "mm10")]

        params = {
            "ATAC-seq": {
                "n_factors": [1, 2, 3],
                "n_variables": [100, 1000, 10000],
                "n_replicates": [1, 2, 5],
            },
            "ChIP-seq": {
                "n_factors": [1, 2, 3],
                "n_variables": [100, 1000, 10000],
                "n_replicates": [1, 2, 5],
            },
            "RNA-seq": {
                "n_factors": [1, 2, 3],
                "n_variables": [100, 1000, 25000],
                "n_replicates": [1, 2, 5],
            },
        }

        for data_type in data_types:
            n_factors = params[data_type]['n_factors'][0]
            n_variables = params[data_type]['n_variables'][0]
            n_replicates = params[data_type]['n_replicates'][0]
            for organism, genome_assembly in genome_assemblies:

                project_name = "{}_{}_{}_{}_{}_{}".format(
                    project_prefix_name, data_type, genome_assembly,
                    n_factors, n_variables, n_replicates
                )
                n_samples = (n_factors * n_replicates) + n_factors

                generate_project(
                    output_dir=tmp_path,
                    project_name=project_name,
                    organism=organism, genome_assembly=genome_assembly,
                    data_type=data_type,
                    n_factors=n_factors, n_replicates=n_replicates, n_variables=n_variables)

                # first edit the defaul path to the annotation sheet
                config = os.path.join(
                    tmp_path, project_name, "metadata", "project_config.yaml")
                c = yaml.safe_load(open(config, 'r'))
                c['metadata']['sample_annotation'] = os.path.abspath(
                    os.path.join(tmp_path, project_name, "metadata", "annotation.csv"))
                c['metadata']['comparison_table'] = os.path.abspath(
                    os.path.join(tmp_path, project_name, "metadata", "comparison_table.csv"))
                yaml.safe_dump(c, open(config, "w"))

                # project and associated analysis
                prj = Project(config)
                a = Analysis(name=project_name, prj=prj)
                assert a.__repr__() == (
                    "Analysis '{}' with {} samples of organism '{}' ({})."
                    .format(project_name, n_samples, organism, genome_assembly))
                assert len(prj.samples) == len(a.samples)
                assert all([x == y for x, y in zip(prj.samples, a.samples)])

                shutil.rmtree(tmp_path)

    def test_analysis_serialization(self, tmp_path):
        import os
        import numpy as np
        import glob

        tmp_path = str(tmp_path)  # for Python2

        pickle_file = os.path.join(tmp_path, "analysis.pickle")
        a = Analysis(pickle_file=pickle_file)
        assert not os.path.exists(pickle_file)
        a.to_pickle()
        assert os.path.exists(pickle_file)
        assert os.stat(pickle_file).st_size > 0

        previous_size = os.stat(pickle_file).st_size
        a.random = np.random.random((100, 100))
        a.to_pickle()
        new_size = os.stat(pickle_file).st_size
        assert new_size > previous_size

        previous_size = os.stat(pickle_file).st_size
        a.random = np.random.random((100, 100))
        a.to_pickle(timestamp=True)
        assert len(
            glob.glob(
                os.path.join(tmp_path, "*.pickle")
                )) == 2

    def test_analysis_loading(self, tmp_path):
        import shutil
        import os

        tmp_path = str(tmp_path)  # for Python2

        pickle_file = os.path.join(tmp_path, "pickle")
        a = Analysis(pickle_file=pickle_file)
        a.secret = "I've existed before"
        a.to_pickle()

        a2 = Analysis(pickle_file=pickle_file, from_pickle=True)
        assert a2.secret == "I've existed before"

        a3 = Analysis()
        a3.update(pickle_file)
        assert a3.secret == "I've existed before"

        a4 = Analysis(pickle_file=pickle_file).from_pickle()
        assert a4.secret == "I've existed before"

        shutil.rmtree(tmp_path)

    def test__overwride_sample_representation(self, analysis):

        prev = analysis.samples[0].__repr__
        Analysis._overwride_sample_representation()
        new = analysis.samples[0].__repr__

        assert prev != new

    def test__check_data_type_is_supported(self):
        assert Analysis._check_data_type_is_supported("ATAC-seq")
        assert Analysis._check_data_type_is_supported("ChIP-seq")
        assert Analysis._check_data_type_is_supported("RNA-seq")
        assert Analysis._check_data_type_is_supported("CNV")
        assert not Analysis._check_data_type_is_supported("Microarray")

    def test__format_string_with_attributes(self):
        t = Analysis()
        t.a = 1
        t.b = ""
        assert "1" == Analysis._format_string_with_attributes(t, "{a}{b}")

    def test__get_data_type(self, analysis):
        assert "ATAC-seq" == analysis._get_data_type()
        assert "ATAC-seq" == analysis._get_data_type(data_type="ATAC-seq")
        assert "RNA-seq" == analysis._get_data_type(data_type="RNA-seq")

        with pytest.raises(ValueError):
            analysis._get_data_type(data_type="Microarray")

        analysis.data_type = None
        with pytest.raises(ValueError):
            analysis._get_data_type()

        del analysis.data_type
        with pytest.raises(AttributeError):
            analysis._get_data_type()
