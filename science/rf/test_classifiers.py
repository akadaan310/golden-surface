import unittest
import numpy as np
try:
 from classifiers import fit_logistic,predict_logistic,session_split
except ImportError:fit_logistic=predict_logistic=session_split=None
class Tests(unittest.TestCase):
 def test_session_split_has_no_window_leakage(self):
  self.assertIsNotNone(session_split,'session split missing')
  groups=np.repeat(np.arange(56),8);train,valid,test=session_split(groups)
  self.assertFalse(set(groups[train])&set(groups[test]));self.assertFalse(set(groups[valid])&set(groups[test]))
 def test_classifier_fits_statistical_signal(self):
  self.assertIsNotNone(fit_logistic,'regularized statistical classifier missing')
  x=np.array([[-2.,0],[-1.,0],[1.,0],[2.,0]]);y=np.array([0,0,1,1]);model=fit_logistic(x,y)
  p=predict_logistic(model,x);self.assertLess(p[0],.5);self.assertGreater(p[-1],.5)
if __name__=='__main__':unittest.main()
