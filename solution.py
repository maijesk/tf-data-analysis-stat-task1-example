import pandas as pd
import numpy as np

chat_id = 700775408

def solution(x: np.array) -> float:
    log_x = np.log(x)
    sigma_sq = np.var(log_x)
    mean_lognormal = np.mean(np.log(x)) - sigma_sq/2 - 407
    return mean_lognormal
