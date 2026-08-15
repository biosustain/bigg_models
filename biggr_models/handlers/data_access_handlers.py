from cobradb.api.escher import ESCHER_MODULE_DEFINITIONS
from biggr_models.handlers import utils
from biggr_models.handlers.object_handlers import MODELS_CLASS_MAP, MODELS_PROPERTY_MAP


class DataAccessPageHandler(utils.BaseHandler):
    template = utils.env.get_template("data_access.html")

    def get(self):
        data = {
            "biggr_address": self.request.host or "bigg.bio",
            "data_models": MODELS_CLASS_MAP.keys(),
            "data_attributes": MODELS_PROPERTY_MAP.keys(),
            "escher_maps": ESCHER_MODULE_DEFINITIONS.keys(),
        }
        self.return_result(data)
