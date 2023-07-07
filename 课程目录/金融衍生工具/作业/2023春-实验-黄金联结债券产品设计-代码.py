import math
import matplotlib.pyplot as plt
import scipy.special
from scipy import linalg
import numpy as np


def CalculateGoldPrice(OldPrice, r=0.03, dt=1/252, sigma=0.2315, ran=0):
    return OldPrice + r*OldPrice * \
        dt+sigma*OldPrice*ran*math.sqrt(dt)


def MonteCarlo(N_path=1000, Gp=200, sigma=0.2315, r=0.03, nr=0.035, F=10000, dt=1/252):
    plt.rc("font", family='YouYuan')  # 显示中文
    FT = np.full(N_path*2+1, F)  # 初始证券价格
    gpath = np.arange(1, N_path*2+1, 1).tolist()
    # print(FT)
    for num in range(1, N_path+1):  # 路径个数

        np.random.seed(num*2+1)  # 设置随机数种子

        gold_price = np.zeros(252*3+1)
        gold_price_2 = np.zeros(252*3+1)
        gold_price[1] = Gp  # 黄金基准价格
        gold_price_2[1] = Gp
        day = np.arange(1, 252*3+1, 1).tolist()
        payoff = nr*F*(math.exp(-r) + math.exp(-r*2) +
                       math.exp(-r*3)) + F * math.exp(-r*3)  # 三年利息的现值 + 本金的现值
        for k in range(1, 252*3):
            ran = np.random.randn(1)
            ran_2 = -ran  # 获得对偶因子
            # 离散形式模拟金价
            gold_price[k+1] = CalculateGoldPrice(gold_price[k], ran=ran)
            gold_price_2[k+1] = CalculateGoldPrice(gold_price_2[k], ran=ran_2)
            if(k == 252*3-1):
                limit_1 = (1+nr)*gold_price[1]
                limit_2 = (1+0.6)*gold_price[1]
                if(gold_price[k+1] <= limit_1):
                    FT[num] = payoff + limit_1*math.exp(-r*3)
                if(limit_1 < gold_price[k+1] and gold_price[k+1] < limit_2):
                    FT[num] = payoff + limit_1*math.exp(-r*3) + 0.3 * \
                        (gold_price[k+1]-limit_1)*math.exp(-r*3)
                if(limit_2 <= gold_price[k+1]):
                    FT[num] = payoff + limit_1 * \
                        math.exp(-r*3) + 0.3*(limit_2 - limit_1)*math.exp(-r*3)
                # 计算路径2
                if(gold_price_2[k+1] <= limit_1):
                    FT[num+N_path] = payoff + limit_1*math.exp(-r*3)
                if(limit_1 < gold_price_2[k+1] and gold_price_2[k+1] < limit_2):
                    FT[num+N_path] = payoff + limit_1*math.exp(-r*3) + 0.3 * \
                        (gold_price_2[k+1]-limit_1)*math.exp(-r*3)
                if(limit_2 <= gold_price_2[k+1]):
                    FT[num+N_path] = payoff + limit_1*math.exp(-r*3) + 0.3 * \
                        (limit_2 - limit_1)*math.exp(-r*3)
        plt.plot(day, gold_price[1:])
        plt.plot(day, gold_price_2[1:])
    plt.title('黄金价格模拟路径')
    plt.grid(True)
    plt.xlabel('时间')
    plt.ylabel('黄金价格')
    plt.show()
    ###
    plt.title('债券价值分布')
    plt.grid(True)
    plt.xlabel('样本路径')
    plt.ylabel('债券价值')
    plt.plot(gpath, FT[1:], 'xk')
    plt.show()
    ###
    x = np.arange(10315, 10350, 0.5).tolist()
    plt.title('债券价值频率')
    plt.grid(True)
    plt.xlabel('债券价值区间')
    plt.ylabel('个数')
    plt.hist(FT, x)
    plt.show()
    return


if __name__ == '__main__':
    MonteCarlo(N_path=1000)
