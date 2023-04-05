import pandas as pd
import numpy as np

chat_id = 700775408

def solution(x: np.array) -> float:
    sigma = np.sqrt(np.log(1 + (np.std(x) / np.mean(x))**2))
    mu = np.log(np.mean(x - 407)) - sigma**2 / 2
    a_est = np.exp(mu)
    x_mean = np.mean(x)
    mu_est_x = np.log(x_mean - 407) - sigma**2 / 2
    a_est_x = np.exp(mu_est_x)
    return a_est_x
