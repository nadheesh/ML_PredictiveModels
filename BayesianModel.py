"""
Copyright 2018 Nadheesh Jihan

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import numpy as np
import pandas as pd
import pymc3 as pm
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.model_selection import KFold
from sklearn.preprocessing import MinMaxScaler
from sklearn.utils import shuffle


class BayesianRBFRegression:

    def fit(self, X, y):
        """
        train model
        :param X:
        :param y:
        :return:
        """

        # bayesian rbf kernel using gaussian processes
        with pm.Model() as self.model:

            ℓ = pm.Gamma("ℓ", alpha=2, beta=1)
            η = pm.HalfCauchy("η", beta=5)

            cov = η ** 2 * pm.gp.cov.Matern52(X.shape[1], ℓ)
            self.gp = pm.gp.Marginal(cov_func=cov)

            σ = pm.HalfCauchy("σ", beta=0.1) # 5, 0.5, 2
            y_ = self.gp.marginal_likelihood("y", X=X, y=y, noise=σ)

            self.map_trace = [pm.find_MAP()]

    def predict(self, X, with_error=False):
        """
        predict using the train model
        :param X:
        :return:
        """
        if not hasattr(self, 'model'):
            raise AttributeError("train the model first")

        with self.model:
            f_pred = self.gp.conditional('f_pred', X)
            pred_samples = pm.sample_ppc(self.map_trace, vars=[f_pred], samples=2000)
            y_pred, uncer = pred_samples['f_pred'].mean(axis=0), pred_samples['f_pred'].std(axis=0)

        if with_error:
            return y_pred, uncer/1000
        return y_pred


def mean_absolute_percentage_error(y_true, y_pred):
    """
    compute mean absolute percentage error
    :param y_true:
    :param y_pred:
    :return:
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def category_to_int(df, columns):
    """
    covert categories to integer codes
    :param df: pandas data-frame
    :param columns: columns to process. can be a string or a list of strings
    :return:
    """
    for col in columns:
        df[col] = df[col].astype('category')

    df[columns] = df[columns].apply(lambda x: x.cat.codes)

    return df


def read_csv(path, scaler):
    """
    read csv given the path

    :param path:
    :param scaler:
    :return:
    """
    df = pd.read_csv(path)

    if path == "Datasets/APIM_Dataset.csv":
        feature_idx = 23  # latency col
        # feature_idx = 29  # throughput col
        label_idx = [0, 1, 2, 3]

        df = df.loc[df["Error %"] < 5]
        df = category_to_int(df, ["Name"])

        X = df.iloc[:, feature_idx]
        y = df.iloc[:, label_idx]

        if not hasattr(scaler, "data_max_"):
            scaler.fit(X)
        _seed = 42

        X = scaler.transform(X)
        y = y.values.flatten()
        return X, y, _seed

    if path == "Datasets/Ballerina_Dataset.csv":
        label_idx = 9  # latency col
        # label_idx = 15  # throughput col
        feature_idx = [1, 3, 4, 5]

        df = df.loc[df["Error %"] < 5]
        df = category_to_int(df, ["Name"])

        X = df.iloc[:, feature_idx]
        y = df.iloc[:, label_idx]

        if not hasattr(scaler, "data_max_"):
            scaler.fit(X)
        _seed = 65

        X = scaler.transform(X)
        y = y.values.flatten()

        return X, y, _seed

    if path == "Datasets/Springboot_Dataset.csv":
        label_idx = 5  # latency col
        # label_idx = 11 # throughput col
        feature_idx = [0, 1, 2, 3, 4]

        df = df.loc[df["error_rate"] < 5]
        df = category_to_int(df, ["use case"])
        df = category_to_int(df, ["collector"])
        df['heap'] = pd.to_numeric(df['heap'].str.replace(r'[a-z]+', ''), errors='coerce')

        X = df.iloc[:, feature_idx]
        y = df.iloc[:, label_idx]

        if not hasattr(scaler, "data_max_"):
            scaler.fit(X)
        _seed = 42

        X = scaler.transform(X)
        y = y.values.flatten()

        return X, y, _seed


def eval_bayesian_rbf(X, y, eval_X, eval_y):
    """
    evaluate linear regression model
    :param X:
    :param y:
    :param eval_X:
    :param eval_y:
    :return: predict_y, error, mse, mape
    """
    lr = BayesianRBFRegression()
    lr.fit(X, y)
    pred_y, error = lr.predict(eval_X, True)

    return pred_y, error, np.sqrt(mean_squared_error(eval_y, pred_y)), mean_absolute_percentage_error(eval_y, pred_y)


if __name__ == '__main__':
    rmse_list = []
    mae_list = []
    mape_list = []

    # file_path = "Datasets/APIM_Dataset.csv"
    file_path = "Datasets/Ballerina_Dataset.csv"
    # file_path = "Datasets/Springboot_Dataset.csv"

    scaler = MinMaxScaler(feature_range=(0, 1))

    _X, _y, seed = read_csv(file_path, scaler)
    _X, _y = shuffle(_X, _y, random_state=seed)

    kf = KFold(n_splits=10, random_state=seed, shuffle=False)
    for train_index, test_index in kf.split(_X):
        pred_bayes, error, rmse_bayes, mape_bayes = eval_bayesian_rbf(np.copy(_X[train_index]), np.copy(_y[train_index]),
                                                                     np.copy(_X[test_index]),  np.copy(_y[test_index]))

        mae_bayes = mean_absolute_error(pred_bayes, _y[test_index])

        rmse_list.append(rmse_bayes)
        mae_list.append(mae_bayes)
        mape_list.append(mape_bayes)

    print("Bayesian RMSE : %f and MAPE :%f and MAE :%f" % (np.mean(rmse_list), np.mean(mape_list), np.mean(mae_list)))
