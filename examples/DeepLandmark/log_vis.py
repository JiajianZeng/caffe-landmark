import argparse
import re
import numpy as np
import matplotlib.pyplot as plt
import sys
import logging

class CaffeLogAnalyzer(object):
  """Caffe log analyzer"""
  def __init__(self, log, start, end, step, loss, info):
    self._framework = 'caffe'
    
    self._log = log
    if self._log:
      self._log = self._log.strip()
      
    self._start = start
    self._end = end
    self._step = step
    self._default_step = 5
    
    self._loss = loss
    if self._loss:
      self._loss = self._loss.strip()
    
    self._info = info
    if self._info:
      self._info = self._info.strip()
    self._framework_re = r'caffe.cpp:[0-9]+\]'
    self._max_framework_match_times = 10
    self._match_framework() 
  @property
  def framework(self):
    return self._framework
  
  @property
  def log(self):
    return self._log
  
  @property
  def framework_re(self):
    return self._framework_re
  
  @property
  def max_framework_match_times(self):
    return self._max_framework_match_times
  
  @property
  def framework_matched(self):
    return self._framework_matched
  
  @property
  def start(self):
    return self._start
  
  @start.setter
  def start(self, start):
    self._start = start

  @property
  def end(self):
    return self._end
  
  @end.setter
  def end(self, end):
    self._end = end
    
  @property
  def step(self):
    return self._step
  
  @step.setter
  def step(self, step):
    self._step = step
    
  @property
  def default_step(self):
    return self._default_step
  
  @default_step.setter
  def default_step(self, default_step):
    self._default_step = default_step
    
  @property
  def loss(self):
    return self._loss
  
  @loss.setter
  def loss(self, loss):
    self._loss = loss
    
  @property
  def info(self):
    return self._info
  
  @info.setter
  def info(self, info):
    self._info = info
    
  def _match_framework(self):
    """Match framework"""
    self._framework_matched = False
    with open(self.log, mode='r') as logs:
      time = 0
      for line in logs:
	if time < self.max_framework_match_times:
	  if re.search(self.framework_re, line):
	    self._framework_matched = True
	    break
	  time += 1
    print "INFO:CaffeLogAnalyzer] Framework match ({})".format(self._framework_matched)
    if not self._framework_matched:
      print "WARNING:CaffeLogAnalyzer] Log file ({}) may not be a caffe log or is corrupted".format(self._log)
      
  def plot(self, x, y, x_label, y_label):
    size = min(x.size, y.size)
    x = x[:size]
    y = y[:size]
    x_max = np.amax(x)
    x_min = np.amin(x)
    if self.start < x_min:
      print "WARNING:CaffeLogAnalyzer] Start iteration ({}) should be greater than the minimum iteration ({})".format(self.start, x_min)
      self.start = x_min
    if self.start > x_max:
      print "ERROR:CaffeLogAnalyzer] Start iteration ({}) should be less than the maximun iteration ({})".format(self.start, x_max)
      return
    if self.end > x_max:
      print "WARNING:CaffeLogAnalyzer] End iteration ({}) should be less than the maximun iteration ({})".format(self.end, x_max)
      self.end = x_max
    if self.end < x_min:
      print "ERROR:CaffeLogAnalyzer] End iteration ({}) should be greater than the minimum iteration ({})".format(self.end, x_min)
      return
    if self.end < self.start:
      print "ERROR:CaffeLogAnalyzer] End iteration ({}) should be greater than or equal to the start iteration ({})".format(self.end, self.start)
      return
    if self.step < 0:
      print "WARNING:CaffeLogAnalyzer] Step ({}) shoule be a positive integer".format(self.step)
      self.step = self.default_step
    
    index = np.zeros((0), np.int32)
    i = j = 0
    while(i < x.size):
      if x[i] >= self.start and x[i] <= self.end:
	if j % self.step == 0:
	  index = np.hstack((index, i))
	j += 1	
      i += 1
    x = x[index]
    y = y[index]
    
    x_max = np.amax(x)
    x_min = np.amin(x)
    y_max = np.amax(y)
    y_min = np.amin(y)
    axis = [x_min, x_max, np.floor(y_min), np.ceil(y_max)]
    plt.plot(x, y, 'r^--')
    plt.axis(axis)
    plt.ylabel(y_label)
    plt.xlabel(x_label)
    plt.show()    

  def analyze_loss(self):
    pass
  
  def analyze_info(self):
    pass
  
  
class CaffeTrainLogAnalyzer(CaffeLogAnalyzer):
  """Caffe train stage log analyzer"""
  
  def __init__(self, log, start, end, step, loss='loss', info=None):
    CaffeLogAnalyzer.__init__(self, log, start, end, step, loss, info)
    self._stage = 'train'
    self._stage_re = r'Iteration ([0-9]+), loss = ([0-9]*\.?[0-9]*)'
    self._loss_re = self.loss + r' = ([0-9]*\.?[0-9]*) \(\* ([0-9]*\.?[0-9]*) = ([0-9]*\.?[0-9]*) loss\)'
    self._lr_re = r'Iteration ([0-9]+), lr = ([0-9]*\.?[0-9]*)'
    self._total_loss = (self.loss == 'loss')
    
  @property
  def stage(self):
    return self._stage
  
  @property
  def stage_re(self):
    return self._stage_re
  
  @property
  def loss_re(self):
    return self._loss_re
  
  @property
  def lr_re(self):
    return self._lr_re
  
  @property
  def total_loss(self):
    return self._total_loss
  
  def _analyze_specified_loss(self):
    """
    Analyze specified loss in trainging stage
    If training iteration not found, then the succeeding processings will not be executed.
    When training iteration found, then it depends:
    1. If specified loss found, the processings finished.
    2. If specified loss not found, it will search for the next training iteration.
    """
    with open(self.log, mode='r') as logs:
      iter_array = np.zeros((0), dtype=np.int32)
      loss_array = np.zeros((0), dtype=np.float32)
      stage_re_matched = False
      iteration = -1
      for line in logs:
	# match training iteration
	if not stage_re_matched:
	  stage_obj = re.search(self.stage_re, line, re.M | re.I)
	  if stage_obj:
	    iteration = int(stage_obj.group(1))
	    stage_re_matched = True
        else:
	  # match specified loss
	  loss_obj = re.search(self.loss_re, line, re.M | re.I)
	  if loss_obj:
	    iter_array = np.hstack((iter_array, iteration))
	    loss_array = np.hstack((loss_array, float(loss_obj.group(3))))
	    stage_re_matched = False
	  else:
	    '''maybe the loss regular expression will be found in the following lines 
	    or it is missed (or not contained in training stage'''
	    # match learning rate
	    lr_obj = re.search(self.lr_re, line, re.M | re.I)
	    if lr_obj:
	      stage_re_matched = False
	    else:
	      # both specified loss and learning rate not found in this training iteration
	      stage_obj = re.search(self.stage_re, line, re.M | re.I)
	      if stage_obj:
	        iteration = int(stage_obj.group(1))
    no_such_loss = (loss_array.size == 0)
    return iter_array, loss_array, no_such_loss
    
  def _analyze_total_loss(self):
    """
    Analyze total loss in training stage
    """
    with open(self.log, mode='r') as logs:
      iter_array = np.zeros((0), dtype=np.int32)
      loss_array = np.zeros((0), dtype=np.float32)
      for line in logs:
	# match training iteration
	stage_obj = re.search(self.stage_re, line, re.M | re.I)
	if stage_obj:
	  iter_array = np.hstack((iter_array, int(stage_obj.group(1))))
	  loss_array = np.hstack((loss_array, float(stage_obj.group(2))))
    no_loss = (loss_array.size == 0)
    return iter_array, loss_array, no_loss
  
  def analyze_loss(self):
    """
    Analyze loss information in training stage
    At present, we only support analyzing one type of loss once.
    """
    if self.total_loss:
      [iter_array, loss_array, no_such_loss] = self._analyze_total_loss()
    else:
      [iter_array, loss_array, no_such_loss] = self._analyze_specified_loss()
         
    if no_such_loss:
      print "WARNING:CaffeTrainLogAnalyzer] Loss ({}) not found in training stage".format(self.loss)
    else:
      print "INFO:CaffeTrainLogAnalyzer] Stage ({}), analyzing loss ({})".format(self.stage, self.loss)
      self.plot(iter_array, loss_array, 'Iteration', self.loss)
    
  def analyze_info(self):
    """
    TODO
    """
    pass
    
    
class CaffeTestLogAnalyzer(CaffeLogAnalyzer):
  """
  Caffe test stage log analyzer
  """
  
  def __init__(self, log, start, end, step, loss='loss', info=None):
    CaffeLogAnalyzer.__init__(self, log, start, end, step, loss, info)
    self._stage = 'test'
    self._stage_re = r'Iteration ([0-9]+), Testing net'
    self._loss_re = self.loss + r' = ([0-9]*\.?[0-9]*) \(\* ([0-9]*\.?[0-9]*) = ([0-9]*\.?[0-9]*) loss\)'
    self._train_stage_re = r'Iteration ([0-9]+), loss = ([0-9]*\.?[0-9]*)'
    if self.info:
      self._info_re = self.info + r' = ([0-9]*\.?[0-9]*)'
    self._loss_group = 3
    self._info_group = 1
    
    
  @property
  def stage(self):
    return self._stage
  
  @property
  def stage_re(self):
    return self._stage_re
  
  @property
  def loss_re(self):
    return self._loss_re
  
  @property
  def info_re(self):
    return self._info_re
  
  @property
  def train_stage_re(self):
    return self._train_stage_re
  
  @property
  def loss_group(self):
    return self._loss_group
  
  @property
  def info_group(self):
    return self._info_group
  
  def _analyze_output(self, output_re, output_group):
    """
    Analyze output in test stage
    If test iteration not found, then the succeeding processings will not be executed.
    When test iteration found, then it depends:
    1. If specified output found, the processings finished.
    2. If specified output not found, it will search for the next test iteration.
    """
    with open(self.log, mode='r') as logs:
      iter_array = np.zeros((0), dtype=np.int32)
      output_array = np.zeros((0), dtype=np.float32)
      stage_re_matched = False
      iteration = -1
      for line in logs:
	# match test iteration
	if not stage_re_matched:
	  stage_obj = re.search(self.stage_re, line, re.M | re.I)
	  if stage_obj:
	    iteration = int(stage_obj.group(1))
	    stage_re_matched = True
	else:
	  # match specified output
	  output_obj = re.search(output_re, line, re.M | re.I)
	  if output_obj:
	    iter_array = np.hstack((iter_array, iteration))
	    output_array = np.hstack((output_array, float(output_obj.group(output_group))))
	    stage_re_matched = False
	  else:
	    '''maybe the output regular expression will be found in the following lines 
	    or it is missed (or not contained in test stage'''
	    # match train iteration
	    train_stage_obj = re.search(self.train_stage_re, line, re.M | re.I)
	    if train_stage_obj:
	      stage_re_matched = False
	    else:
	      # both the specified output and the training iteration following the test iteration not found
	      stage_obj = re.search(self.stage_re, line, re.M | re.I)
	      if stage_obj:
	        iteration = int(stage_obj.group(1))
    no_such_output = (output_array.size == 0)
    return iter_array, output_array, no_such_output
    
  def analyze_loss(self):
    """
    Analyze output loss in test stage
    """
    [iter_array, loss_array, no_such_loss] = self._analyze_output(self.loss_re, self.loss_group)
    if no_such_loss:
      print "WARNING:CaffeTestLogAnalyzer] Loss ({}) not found in test stage".format(self.loss)
    else:
      print "INFO:CaffeTestLogAnalyzer] Stage ({}), analyzing loss ({})".format(self.stage, self.loss)
      self.plot(iter_array, loss_array, 'Iteration', self.loss)
      
  def analyze_info(self):
    """
    Analyze output info in test stage
    """
    [iter_array, info_array, no_such_info] = self._analyze_output(self.info_re, self.info_group)
    if no_such_info:
      print "WARNING:CaffeTestLogAnalyzer] Info ({}) not found in test stage".format(self.info)
    else:
      print "INFO:CaffeTestLogAnalyzer] Stage ({}), analyzing output ({})".format(self.stage, self.info)
      self.plot(iter_array, info_array, 'Iteration', self.info)
      


def parse_args():
    parser = argparse.ArgumentParser(description='Analyze a log file.')
    parser.add_argument('--log',
                        help='log file',
                        default=None, type=str)
    # At present, we only support caffe
    # TODO
    # support for other deep learning frameworks
    parser.add_argument('--framework', 
			help='deep learning framework producing the log file',
			choices=['caffe'],
			default='caffe', type=str)
    parser.add_argument('--stage', 
			help='stage (TRAIN or TEST)',
			choices=['train', 'test'],
			default='train', type=str)
    parser.add_argument('--start',
                        help='start iteration',
                        default=None, type=int)
    parser.add_argument('--end',
                        help='end iteration',
                        default=None, type=int)
    parser.add_argument('--step', 
                        help='display step',
                        default=1, type=int)
    parser.add_argument('--loss',
                        help='loss to be analyzed',
                        default=None, type=str)
    parser.add_argument('--info',
			help='output information in corresponding stage to be analyzed',
			default=None, type=str)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    return args
  
if __name__ == '__main__':
    args = parse_args()
    if args.log:
      if args.stage == 'train':
	if args.loss:
	  la = CaffeTrainLogAnalyzer(args.log, args.start, args.end, args.step, loss=args.loss)
	else:
	  la = CaffeTrainLogAnalyzer(args.log, args.start, args.end, args.step, loss='loss')
	la.analyze_loss()
      else:
        if args.loss:
	  la = CaffeTestLogAnalyzer(args.log, args.start, args.end, args.step, loss=args.loss)
	  la.analyze_loss()
	elif args.info:
	  la = CaffeTestLogAnalyzer(args.log, args.start, args.end, args.step, info=args.info)
	  la.analyze_info()
	else:
	  print "ERROR:CaffeTestLogAnalyzer] Both loss and info are not specified"
    else:
      print "ERROR:CaffeLogAnalyzer] No log file specified"
    