
#segementation dynamic related 
MIN_MASK_SZIE = 15

#tracking related
DIVISION_COST = -0.2
APPEAR_COST = -1
DISAPPEAR_COST = -1

#segementation predict related 
SEGEMENTATION_PARAMS_OMNIPOSE = {
    'rescale': None, # upscale or downscale your images, None = no rescaling 
    'omni': True, # we can turn off Omnipose mask reconstruction, not advised 
    'affinity_seg': False, # new feature, stay tuned...
    'compute_masks': False
}

SEGEMENTATION_PARAMS_CELLPOSE = {
    'rescale': None, # upscale or downscale your images, None = no rescaling 
    'compute_masks': False
}

