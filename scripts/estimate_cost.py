"""Scenario calculator, not a prediction of model quality or sustained throughput."""
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--parameters',type=float,required=True);p.add_argument('--tokens',type=float,required=True);p.add_argument('--tflops',type=float,default=100);p.add_argument('--usd-per-gpu-hour',type=float,default=2.89);p.add_argument('--overhead',type=float,default=1.3);p.add_argument('--runs',type=float,default=1);a=p.parse_args()
assert min(a.parameters,a.tokens,a.tflops,a.usd_per_gpu_hour,a.overhead,a.runs)>0
hours=6*a.parameters*a.tokens/(a.tflops*1e12*3600)*a.overhead*a.runs
print(json.dumps({'assumptions':vars(a),'gpu_hours':hours,'compute_usd':hours*a.usd_per_gpu_hour,'excludes':'data generation, storage, taxes, engineering labor; 6ND approximation excludes explicit attention overhead'},indent=2))
