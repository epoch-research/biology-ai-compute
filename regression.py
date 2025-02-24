import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from utils import *


def fit_ols_regression(data, features, target, logy=False):
    """
    Fits an OLS regression model using the formula API, automatically handling feature names and constant features.

    Parameters:
    - data (pd.DataFrame): The input data containing features and target.
    - features (list of str): List of feature column names.
    - target (str): The target column name.
    - logy (bool): Whether to apply logarithmic transformation to the target.

    Returns:
    - results (RegressionResultsWrapper): The fitted OLS model.
    """
    # Drop rows with missing values in features or target
    data = data.dropna(subset=features + [target])

    # Apply log transformation to the target if specified
    if logy:
        data[target] = np.log10(data[target])

    # Construct the formula for the model
    formula = f"{target} ~ " + " + ".join(features)

    # Fit the OLS model using the formula API
    model = smf.ols(formula=formula, data=data).fit()

    return model


def get_predictions(model, data, features):
    """
    Generates predictions using the fitted OLS model.

    Parameters:
    - model (RegressionResultsWrapper): The fitted OLS model.
    - data (pd.DataFrame): The input data for prediction. Must include all features used in the model.

    Returns:
    - predictions (np.ndarray): The predicted values.
    """
    # Extract the feature names used in the model from the formula
    # Exclude the intercept (the first parameter)
    model_features = model.params.index[1:]
    
    # Identify missing features in the prediction data
    missing_features = set(model_features) - set(data.columns)
    if missing_features:
        raise ValueError(f"The following required features are missing from the prediction data: {missing_features}")

    # Make predictions
    predictions = model.predict(data)

    return predictions.to_numpy()


def get_prediction_df(model, data, features):
    X = data[features].to_numpy()
    X = sm.add_constant(X)
    pred_df = model.get_prediction(X).summary_frame()
    pred_df[features] = data[features]
    return pred_df


def print_growth_rates(model):
    print(f"Adj. R^2={model.rsquared_adj:.2f}")
    print(f"{model.params[1]:.2f} OOMs/year (95% CI: {model.conf_int()[1][0]:.2f}, {model.conf_int()[1][1]:.2f})")
    print(f"{ooms_to_factor_per_year(model.params[1]):.1f}x/year (95% CI: {ooms_to_factor_per_year(model.conf_int()[1][0]):.1f}x, {ooms_to_factor_per_year(model.conf_int()[1][1]):.1f}x)")
    print(f"doubling time of {ooms_to_doubling_time_months(model.params[1]):.0f} months (95% CI: {ooms_to_doubling_time_months(model.conf_int()[1][1]):.0f}, {ooms_to_doubling_time_months(model.conf_int()[1][0]):.0f})")


def regression_slope_t_test(data1, data2, features, target, logy=False, adj_corr=True):
    data1 = data1.dropna(subset=features + [target])
    X1 = data1[features].to_numpy()
    X1 = sm.add_constant(X1)  # Add a constant term to the features
    y1 = data1[target].to_numpy()

    data2 = data2.dropna(subset=features + [target])
    X2 = data2[features].to_numpy()
    X2 = sm.add_constant(X2)
    y2 = data2[target].to_numpy()

    common_systems = data1['System'].isin(data2['System']) & data2['System'].isin(data1['System'])
    if any(common_systems):
        data12 = data1.loc[common_systems].dropna(subset=features + [target])
        X12 = data12[features].to_numpy()
        X12 = sm.add_constant(X12)
        y1_common = data1.loc[common_systems][target].to_numpy()
        y2_common = data2.loc[common_systems][target].to_numpy()

    if logy:
        y1 = np.log10(y1)
        y2 = np.log10(y2)
        if any(common_systems):
            y1_common = np.log10(y1_common)
            y2_common = np.log10(y2_common)

    # Separate regressions
    model1 = sm.OLS(y1, X1).fit()
    model2 = sm.OLS(y2, X2).fit()

    # Get the slopes and standard errors
    b1, SE1 = model1.params[1], model1.bse[1]
    b2, SE2 = model2.params[1], model2.bse[1]

    print(f"Slope 1: {b1:.2f} (SE: {SE1:.2f})")
    print(f"Slope 2: {b2:.2f} (SE: {SE2:.2f})")

    # get residuals of overlapping data as predicted by each model
    if any(common_systems):
        residuals_model1 = y1_common - model1.predict(exog=X12)
        residuals_model2 = y2_common - model2.predict(exog=X12)

    # get the correlation coefficient between residuals according to each model
    if adj_corr and any(common_systems):
        rho = np.corrcoef(residuals_model1, residuals_model2)[0, 1]
    else:
        rho = 0

    # Calculate the test statistic
    t_stat = (b1 - b2) / np.sqrt(SE1 ** 2 + SE2 ** 2 - 2 * SE1 * SE2 * rho)

    # Degrees of freedom
    df1 = X1.shape[0] - 2
    df2 = X2.shape[0] - 2
    df = df1 + df2

    # Calculate the p-value
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))

    print(f"Correlation of residuals: {rho:.2f}")
    print(f"Test statistic: {t_stat:.2f}")
    print(f"p-value: {p_value:.2f}")
