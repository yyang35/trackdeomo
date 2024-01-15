import mip
import logging
import numpy as np
import time
from scipy.sparse import dok_matrix, csr_matrix

from bactrack import config
from .solver import Solver

MIP_solver_logger = logging.getLogger(__name__)

class MIPSolver(Solver):
    def __init__(self, weight_matrix, hier_arr, mask_penalty = None):

        self.hier_arr = hier_arr
        self.weight_matrix = weight_matrix.tocsr()
        self.seg_N = hier_arr[-1]._index[-1]
        self.model =  mip.Model(sense=mip.MAXIMIZE, solver_name=mip.GUROBI)
        self.mask_penalty = mask_penalty
        self.nodes = None
        self.edges = None
        self._build_mip()
        

    def solve(self):
        
        self.model.optimize()
        n = np.asarray([i for i, node in enumerate(self.nodes) if node.x > 0.5], dtype=int)
        e = np.asarray([i for i, edge in enumerate(self.edges) if edge.x > 0.5], dtype=int)
        
        row, col = self.weight_matrix.nonzero()
        e_matrix = dok_matrix(self.weight_matrix.shape)
        for r, c in zip(row[e], col[e]):
            e_matrix[r, c] = 1

        return n, e_matrix


    def _build_mip(self):
        MIP_solver_logger.info("Setting up MIP problem")
        t1 = time.time()

        self.nodes, self.edges = self._basic_mip()
        self._add_hierarchy_conflict()
        if self.mask_penalty is not None:
             self.model.objective -= mip.xsum(self.mask_penalty * self.nodes)

        t_used = time.time() - t1
        MIP_solver_logger.info(f"MIP problem set up: time used {t_used} sec")


    def _basic_mip(self):
       
        frames = np.array([node.frame for hier in self.hier_arr for node in hier.all_nodes()])
        not_start = frames != 0
        not_end = frames != np.max(frames)

        # set objective
        nodes = self.model.add_var_tensor((self.seg_N,), name="nodes", var_type=mip.BINARY)
        appearances = self.model.add_var_tensor((self.seg_N,), name="appear", var_type=mip.BINARY)
        disappearances = self.model.add_var_tensor((self.seg_N,), name="disappear", var_type=mip.BINARY )
        divisions = self.model.add_var_tensor((self.seg_N,), name="division", var_type=mip.BINARY)
        edges = self.model.add_var_tensor((self.weight_matrix.count_nonzero(),), name="edges", var_type=mip.BINARY)

        self.model.objective = (
            mip.xsum( divisions * config.DIVISION_COST )
            + mip.xsum( (appearances * not_start) * config.APPEAR_COST)
            + mip.xsum( (disappearances * not_end) * config.DISAPPEAR_COST)
            + mip.xsum( self.weight_matrix.data * edges)
        )
        
        # set constrain 
        rows, cols = self.weight_matrix.nonzero() 
        for i in range(self.seg_N):
            target_indices = np.where(rows == i)[0]
            source_indices = np.where(cols == i)[0]
            # single incoming node
            self.model.add_constr(mip.xsum(edges[source_indices]) + appearances[i] == nodes[i])
            # flow conservation
            self.model.add_constr(nodes[i] + divisions[i] == mip.xsum(edges[target_indices]) + disappearances[i])
            # check this 
            self.model.add_constr(nodes[i] >= divisions[i])

        return nodes, edges


    def _add_hierarchy_conflict(self):
        for hier in self.hier_arr:
            for node in hier.all_nodes():
                for super in node.all_supers():
                    self.model.add_constr(self.nodes[node.index] + self.nodes[super] <= 1)
       