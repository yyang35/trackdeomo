from enum import Enum
import util
import logging

# To avoid any cyclic import, packages are import locally inside method. 


core_logger = logging.getLogger(__name__)


class ModelEnum(Enum):
    OMNIPOSE = "Omnipose"
    CELLPOSE = "Cellpose"


def process(basedir, hypermodel: ModelEnum = None, chans = [0,0], submodel = None,):

    from config import SEGEMENTATION_PARAMS

    hypermodel = ModelEnum.OMNIPOSE if hypermodel is None else hypermodel

    if hypermodel == ModelEnum.OMNIPOSE:
        import omnipose
        from cellpose_omni import io, transforms, models, core
        from omnipose.utils import normalize99
    elif hypermodel == ModelEnum.CELLPOSE:
        import cellpose
        from cellpose import io, transforms, models, core
        from cellpose.transforms import normalize99
    else:
        raise Exception("No support on model {hypermodel}")
    
    if submodel not in models.MODEL_NAMES:
        core_logger.info(
            "Model {submodel} isn't in {hypermodel.value}'s model zoo. Use default model"
        )
        submodel = None
    
    use_GPU = core.use_gpu()
    model = models.CellposeModel(gpu=use_GPU, model_type = submodel)
    
    imags = util.load(basedir, io)
    params = SEGEMENTATION_PARAMS[hypermodel]

    # segementation model predict field (distance field + flow field), but does not compute mask
    params['compute_masks'] = False
    params['channels'] = chans
    _, flows, _ = model.eval(imags, **params)

    core_logger.info("Segementation: predicting fields finish.")

    # base on predicted field, run dynamic integration, computer segementation hierarchy
    hier_arr = []
    for flow in flows:
        hier_arr.append(compute_masks(flow))

    core_logger.info("Segementation hierarchy builded.")

    run_tracking(hier_arr)


def run_tracking(hier_arr):

    from hierarchy import Hierarchy
    from tracking import solve

    total_num = Hierarchy.label_hierarchy_array(hier_arr)
    solve(hier_arr, seg_num = total_num, cost_func_name = "overlap"):

    pass


def compute_masks(flow):

    from segementation import computer_hierarchy

    [RGB_dP, dP, cellprob, p, bd, tr, affinity, bounds] = flow
    dP, cellprob = dP.squeeze(), cellprob.squeeze()
    hier = computer_hierarchy(cellprob, dP)

    return hier







