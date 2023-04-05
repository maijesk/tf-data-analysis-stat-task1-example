import pandas as pd
import numpy as np

chat_id = 700775408

def solution(samples: np.array) -> float:
    sigma = np.sqrt(np.log(1 + (np.std(samples) / np.mean(samples))**2))
    mu = np.log(np.mean(samples)) - sigma**2 / 2
    a_est = np.exp(mu)
    sample_mean = np.mean(samples)
    mu_est_sample = np.log(sample_mean - 407) - sigma**2 / 2
    a_est_sample = np.exp(mu_est_sample)  
    return a_est_sample
