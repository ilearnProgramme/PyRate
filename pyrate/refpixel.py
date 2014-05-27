'''
Functions for finding the reference pixel in PyRate.
Author: Ben Davies
'''

import config

from numpy import array, isnan, std, mean, sum as nsum


DO_REFPIX_SEARCH = -1 # TODO: better name for this flag



def ref_pixel(params, ifgs):
	'''
	Returns (y,x) reference pixel coordinate from given ifgs.
	
	If the config file REFX or REFY values are empty or subzero, the search for
	the reference pixel is performed. If the REFX|Y values are within the bounds
	of the raster, a search is not performed. REFX|Y values outside the upper
	bounds cause an exception.
	
	params: dict of key/value pairs from config file
	ifgs: sequence of interferograms
	'''
	if len(ifgs) < 1:
		msg = 'Reference pixel search requires 2+ interferograms'
		raise RefPixelError(msg)
	
	head = ifgs[0]	
	refx = params.get(config.REFX, DO_REFPIX_SEARCH)
	refy = params.get(config.REFY, DO_REFPIX_SEARCH)
	
	# sanity check any specified ref pixel settings
	# unlikely, but possible the refpixel can be (0,0) 
	if refx > head.WIDTH - 1:
		raise ValueError("Invalid reference pixel X coordinate: %s" % refx)
	if refy > head.FILE_LENGTH - 1:
		raise ValueError("Invalid reference pixel Y coordinate: %s" % refy)
	
	if refx >= 0 and refy >= 0:
		return (refy, refx) # reuse preset ref pixel

	check_ref_pixel_params(params, head)

	# pre-calculate useful amounts
	refnx = params[config.REFNX]
	refny = params[config.REFNY]
	chipsize = params[config.REF_CHIP_SIZE]
	radius = chipsize / 2
	phase_stack = array([i.phase_data for i in ifgs]) # TODO: mem efficiencies?
	thresh = params[config.REF_MIN_FRAC] * chipsize * chipsize
	min_sd = float("inf") # dummy start value

	# do window searches across dataset, central pixel of stack with smallest
	# mean is the reference pixel
	for y in _step(head.FILE_LENGTH, refny, radius):
		for x in _step(head.WIDTH, refnx, radius):
			data = phase_stack[:, y-radius:y+radius+1, x-radius:x+radius+1]
			valid = [nsum(~isnan(i)) > thresh for i in data]

			if all(valid): # ignore if 1+ ifgs have too many incoherent cells
				sd = [std( i[~isnan(i)] ) for i in data]
				mean_sd = mean(sd)
				if mean_sd < min_sd:
					min_sd = mean_sd
					refy, refx = y, x

	if (refy, refx) == (DO_REFPIX_SEARCH, DO_REFPIX_SEARCH):
		raise RefPixelError("Could not find a reference pixel")
	return refy, refx


def check_ref_pixel_params(params, head):
	'''Validates reference pixel search parameters. head is any Ifg.'''

	def missing_option_error(option):
		'''Internal convenience function for raising similar errors.'''
		msg = "Missing '%s' in configuration options" % option
		raise config.ConfigException(msg)

	# sanity check chipsize setting
	chipsize = params.get(config.REF_CHIP_SIZE)
	if chipsize is None:
		missing_option_error(config.REF_CHIP_SIZE)

	if chipsize < 3 or chipsize > head.WIDTH or (chipsize % 2 == 0):
		msg = "Chipsize setting must be >=3 and at least <= grid width"
		raise ValueError(msg)

	# sanity check minimum fraction
	min_frac = params.get(config.REF_MIN_FRAC)
	if min_frac is None:
		missing_option_error(config.REF_MIN_FRAC)

	if min_frac < 0.0 or min_frac > 1.0:
		raise ValueError("Minimum fraction setting must be >= 0.0 and <= 1.0 ")

	# sanity check X|Y steps
	refnx = params.get(config.REFNX)
	if refnx is None:
		missing_option_error(config.REFNX)

	max_width = (head.WIDTH - (chipsize-1))
	if refnx < 1 or refnx > max_width:
		msg = "Invalid refnx setting, must be > 0 and <= %s"
		raise ValueError(msg % max_width)

	refny = params.get(config.REFNY)
	if refny is None:
		missing_option_error(config.REFNY)

	max_rows = (head.FILE_LENGTH - (chipsize-1))
	if refny < 1 or refny > max_rows:
		msg = "Invalid refny setting, must be > 0 and <= %s"
		raise ValueError(msg % max_rows)


def _step(dim, ref, radius):
	'''
	Helper func: returns xrange obj of axis indicies for a search window.
	
	dim: total length of the grid dimension
	ref: the desired number of steps
	radius: the number of cells from the centre of the chip eg. (chipsize / 2)
	'''
	if ref == 1:
		# centre a single search step
		return xrange(dim // 2, dim, dim) # fake step to ensure single xrange value

	max_dim = dim - (2*radius) # max possible number for refn(x|y)
	if ref == 2: # handle 2 search windows, method below doesn't cover the case
		return [radius, dim-radius-1]

	step = max_dim // (ref-1)
	return xrange(radius, dim, step)


class RefPixelError(Exception):
	'''Generic exception for reference pixel errors'''
	pass
