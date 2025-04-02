from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException, 
                       QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
                       QgsProcessingParameterNumber)
from scipy.stats import chisquare, norm
import numpy as np

class TesteAleatoriedadeProcessingAlgorithm(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            'layer_input', 'Layer for randomness test (polygon): Systematized Data', 
            types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterField(
            'labels', 'Labels to p-value (field used to aggregate - step1)', '', 'layer_input', QgsProcessingParameterField.Any))
        self.addParameter(QgsProcessingParameterField(
            'expected_vals', 'Expected Values Field (expected_vals)', '', 'layer_input'))
        self.addParameter(QgsProcessingParameterField(
            'observed_vals', 'Observed Values Field (observed_vals)', '', 'layer_input'))
        self.addParameter(QgsProcessingParameterNumber(
            'alpha', 'Alpha value(significance level)', QgsProcessingParameterNumber.Double,
            defaultValue=0.05))

    @staticmethod
    def critical_values(alpha):
        upper_limit = norm.ppf(1 - alpha / 2)
        lower_limit = norm.ppf(alpha / 2)
        return upper_limit, lower_limit

    @staticmethod
    def normalized_values(values):
        total = sum(values)
        return [value / total for value in values] if total != 0 else values

    def processAlgorithm(self, parameters, context, feedback):
        data = self.parameterAsVectorLayer(parameters, 'layer_input', context)
        expected_vals = self.parameterAsString(parameters, 'expected_vals', context)
        observed_vals = self.parameterAsString(parameters, 'observed_vals', context)
        labels = self.parameterAsString(parameters, 'labels', context)
        alpha = self.parameterAsDouble(parameters, 'alpha', context)

        expected = []
        observed = []
        label = []

        for feature in data.getFeatures():
            exp = feature[expected_vals]
            obs = feature[observed_vals]
            label.append(feature[labels])
            if isinstance(exp, (int, float)) and isinstance(obs, (int, float)):
                expected.append(float(exp))
                observed.append(float(obs))

        expected = self.normalized_values(expected)
        observed = self.normalized_values(observed)

        chi2, p_valor = chisquare(observed, f_exp=expected)
        num_tests = len(expected)
        bonferroni_p_value = p_valor * num_tests
        bonferroni_alpha = alpha / num_tests

        bonferroni_upper_limit, bonferroni_lower_limit = self.critical_values(bonferroni_alpha)
        alpha_upper_limit, alpha_lower_limit = self.critical_values(alpha)

        # Generate message for chi-square test results without Bonferroni correction
        mensagem = f"Chi-Square Test Statistic (without Bonferroni correction): {chi2:.4f}\n"
        mensagem += f"p-value: {p_valor:.6f}\n"
        mensagem += f"Critical values (without Bonferroni correction) (alpha {alpha:.3f}): Upper limit: {alpha_upper_limit:.3f}, Lower limit: {alpha_lower_limit:.3f}\n"

        res_std = (np.array(observed) - np.array(expected)) / np.sqrt(expected)
        res_std_lb = list(zip(label, res_std))

        mensagem_excessos = "Residual values that exceed critical values:\n"
        contagem_excessos = 0

        for label1, res in res_std_lb:
            if res > alpha_upper_limit or res < alpha_lower_limit:  # Use appropriate critical values here
                mensagem_excessos += f"The residue observed in theme '{label1}' exceeds the limit of critical values of {res:.4f}. This value indicates that it influences the point pattern.\n"
                contagem_excessos += 1

        if contagem_excessos == 0:
            mensagem_excessos = "None of the themes analyzed has residual values that exceed critical limits.\n"

        mensagem += mensagem_excessos
        if p_valor < alpha:
            mensagem += "Reject the null hypothesis: There is a significant difference between expected and observed values."
        else:
            mensagem += "Fail to reject the null hypothesis: No significant difference was observed between expected and observed values."
        
        feedback.pushInfo("Chi-Square goodness-of-fit Test (without Bonferroni correction):\n"+ mensagem)
        
        # end message for results without Bonferroni correction
        
        feedback.pushInfo(" ")
        feedback.pushInfo(" ")        
        
        # Generate message for chi-square test with Bonferroni correction
        mensagem_bonferroni = f"Chi-Square Test Statistic (with Bonferroni correction): {chi2:.4f}\n"
        mensagem_bonferroni += f"Corrected p-value (Bonferroni correction): {bonferroni_p_value:.6f}\n"
        mensagem_bonferroni += f"Critical values with Bonferroni (corrected alpha {bonferroni_alpha:.3f}): Upper limit: {bonferroni_upper_limit:.3f}, Lower limit: {bonferroni_lower_limit:.3f}\n"

        mensagem_excessos_bonferroni = "Residual values that exceed critical values (with Bonferroni correction):\n"
        contagem_excessos_bonferroni = 0

        for label2, res in res_std_lb:
            if res > bonferroni_upper_limit or res < bonferroni_lower_limit:
                mensagem_excessos_bonferroni += f"The residue observed in theme '{label2}' exceeds the limit of critical values of {res:.4f}. This value indicates that it influences the point pattern.\n"
                contagem_excessos_bonferroni += 1

        if contagem_excessos_bonferroni == 0:
            mensagem_excessos_bonferroni = "None of the themes analyzed has residual values that exceed critical limits.\n"

        mensagem_bonferroni += mensagem_excessos_bonferroni

        if bonferroni_p_value < bonferroni_alpha:
            mensagem_bonferroni += "Reject the null hypothesis with Bonferroni correction: There is a significant difference between expected and observed values."
        else:
            mensagem_bonferroni += "Fail to reject the null hypothesis with Bonferroni correction: No significant difference was observed between expected and observed values."
        
        feedback.pushInfo("Chi-Square goodness-of-fit Test (with Bonferroni correction)\n" + mensagem_bonferroni)

        return {}

    def name(self):
        return 'Spatial_Randomness_Test_p2'

    def displayName(self):
        return 'Spatial Randomness Part 2: Chi-square goodness-of-fit Test'

    def group(self):
        return 'Randomness Point Pattern Test (RPPT)'

    def groupId(self):
        return 'Randomness Point Pattern Test (RPPT)'

    def createInstance(self):
        return TesteAleatoriedadeProcessingAlgorithm()

    def shortHelpString(self):
        return ("<font size='4'><b>This tool tests for spatial randomness in point patterns within polygons using the Chi-square test, providing results both with and without Bonferroni correction.</b></font>")

    def helpUrl(self):
        return 'https://yourorganization.com/help'
