from cobradb.models import Genome
from biggr_models.handlers import utils
from biggr_models.queries import genome_queries, object_queries


class GenomeHandler(utils.BaseHandler):
    template = utils.env.get_template("genome.html")

    def get(self, genome_ref_string):
        if self.is_api_request():
            return self.return_object(
                object_queries.get_genome_object_by_accession, genome_ref_string
            )
        result = utils.safe_query(
            genome_queries.get_genome_and_models, genome_ref_string
        )
        result["breadcrumbs"] = [
            ("Home", "/"),
            ("Genomes", "/genomes/"),
            (result["name"], f"/genomes/{genome_ref_string}"),
        ]
        self.return_result(result)


class GenomeListViewHandler(utils.DataHandler):
    title = "Genomes"
    column_specs = [
        utils.DataColumnSpec(
            Genome.accession_value,
            "ID",
            hyperlink="/genomes/${row['genome__accession_type']}:${row['genome__accession_value']}",
        ),
        utils.DataColumnSpec(Genome.organism, "Organism"),
        utils.DataColumnSpec(
            Genome.accession_type,
            "Type",
        ),
    ]

    def breadcrumbs(self):
        return [
            ("Home", "/"),
            ("Genomes", "/genomes/"),
        ]
