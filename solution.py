import pandas as pd
import numpy as np

chat_id = 700775408 # Ваш chat ID, не меняйте название переменной

def solution(x: np.array) -> float:  
    return np.log(x-407).mean()
