from enum import Enum
import logging
import numpy as np
from tqdm import tqdm

from .config import SEGEMENTATION_PARAMS_OMNIPOSE, SEGEMENTATION_PARAMS_CELLPOSE
from .tracking import Weight, Solver
from . import io

# To avoid any cyclic import, packages are import locally inside method. 


core_logger = logging.getLogger(__name__)


class ModelEnum(Enum):
    OMNIPOSE = "Omnipose"
    CELLPOSE = "Cellpose"

SEGEMENTATION_PARAMS = {
    ModelEnum.OMNIPOSE: SEGEMENTATION_PARAMS_OMNIPOSE,
    ModelEnum.CELLPOSE: SEGEMENTATION_PARAMS_CELLPOSE
}

def compute_hierarchy(
        data, 
        hypermodel: ModelEnum = None, 
        chans = [0,0], 
        submodel = None, 
):
    hypermodel = ModelEnum.OMNIPOSE if hypermodel is None else hypermodel

    if hypermodel == ModelEnum.OMNIPOSE:
        import omnipose
        from cellpose_omni import io as seg_io
        from cellpose_omni import transforms, models, core
        from omnipose.utils import normalize99
    elif hypermodel == ModelEnum.CELLPOSE:
        import cellpose
        from cellpose import io as seg_io
        from cellpose import transforms, models, core
        from cellpose.transforms import normalize99
    else:
        raise Exception("No support on model {hypermodel}")
    
    if submodel not in models.MODEL_NAMES:
        core_logger.info(
            "Model {submodel} isn't in {hypermodel.value}'s model candidates. Use default model"
        )
        submodel = None
    
    use_GPU = core.use_gpu()
    model = models.CellposeModel(gpu=use_GPU, model_type=submodel)
    
    imags = io.load(data, seg_io)
    params = SEGEMENTATION_PARAMS[hypermodel]

    # Step1. segementation model predict field (distance field + flow field), but does not compute mask
    params['compute_masks'] = False
    params['channels'] = chans
    _, flows, _ = model.eval(imags, **params)

    core_logger.info("Segementation: predicting fields finish.")

    # Step2. base on predicted field, run dynamic integration, computer segementation hierarchy
    hier_arr = []
    for flow in tqdm(flows):
        hier_arr.append(compute_masks(flow))

    core_logger.info("Segementation hierarchy builded.")

    # Step3. mark the freatures of segementations in hierarchy
    from .hierarchy import Hierarchy 
    Hierarchy.label_hierarchy_array(hier_arr)
    Hierarchy.compute_segementation_metrics(hier_arr)
    
    core_logger.info("Labeled feature of each segementation in hierarchy.")

    return hier_arr


def run_tracking(hier_arr, solver_name = "mip_solver", weight_name = "overlap_weight", **kwargs):
    from .tracking import MIPSolver, GraphSolver
    from .tracking import IOUWeight, OverlapWeight, DistanceWeight

    solvers = {
        "mip_solver": MIPSolver,
        "graph_solver": GraphSolver,
    }

    weights = {
        "iou_weight":  IOUWeight,
        "overlap_weight": OverlapWeight,
        "distance_weight": DistanceWeight,
    }

    Solver = solvers.get(solver_name.lower())
    if not Solver:
         raise ValueError(f"Solver '{solver_name}' not found")

    Weight = weights.get(weight_name.lower())
    if not Weight:
         raise ValueError(f"Weight '{weight_name}' not found")
    
    weight = Weight(hier_arr, **kwargs)
    solver = Solver(weight.weight_matrix, hier_arr, mask_penalty = weight.mask_penalty)
    nodes, edges = solver.solve()

    return nodes, edges

    

def run_postprocess(hier_arr, n, edges):
    from .io import format_output, store_output
    mask_arr, edge_df  = format_output(hier_arr, n, edges)
    return mask_arr, edge_df


def compute_masks(flow):

    from .segementation import computer_hierarchy

    [RGB_dP, dP, cellprob, p, bd, tr, affinity, bounds] = flow
    dP, cellprob = dP.squeeze(), cellprob.squeeze()
    hier = computer_hierarchy(cellprob, dP)

    return hier







