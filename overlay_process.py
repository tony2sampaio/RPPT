from qgis.core import QgsProcessingUtils, QgsField
from PyQt5.QtCore import QVariant
from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
from qgis.gui import QgsExpressionBuilderDialog #será usado depois
from qgis.PyQt.QtWidgets import QInputDialog, QMessageBox  #será usado depois

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterBoolean,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFeatureSink)
from qgis import processing

class AleatorioProcessingAlgorithm(QgsProcessingAlgorithm):

    USE_CONCAVE = 'USE_CONCAVE'
    CONCAVE_PARAMETER = 'CONCAVE_PARAMETER'
    USE_MIN_BOUNDING = 'USE_MIN_BOUNDING'
    MIN_BOUNDING_TYPE = 'MIN_BOUNDING_TYPE'

    def __init__(self):
        super(AleatorioProcessingAlgorithm, self).__init__()

    def initAlgorithm(self, config=None):
    
        self.addParameter(QgsProcessingParameterFeatureSource('layer_to_analysis', 
            'Layer to be analyzed (points)', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_CONCAVE, 
            'Use adjusted delimitation (Concave Hull)',           
            defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CONCAVE_PARAMETER, 
            'Area Adjustment Value (0-1) to Concave Hull', 
            type=QgsProcessingParameterNumber.Double, 
            minValue=0, 
            maxValue=1, 
            defaultValue=0.3, 
            optional=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_MIN_BOUNDING, 
            'Minimum Bounding Geometry', 
            defaultValue=False))
        self.addParameter(QgsProcessingParameterEnum(
            self.MIN_BOUNDING_TYPE, 
            'Use Minimum Bounding Geometry',
            options=['Envelope (bounding box)', 'Minimal oriented rectangle', 'Minimal enclosing circle'],
            defaultValue=0,
            optional=True))
        self.addParameter(QgsProcessingParameterNumber('define_buffer', 
            'Defines the width of the study area around the points', 
            type=QgsProcessingParameterNumber.Double, minValue=0, defaultValue=1000))
        self.addParameter(QgsProcessingParameterFeatureSource('driver', 
            'Driver - layer (Polygon)', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterField('field_aggreg', 
            'Field to aggregate', type=QgsProcessingParameterField.Any, 
            parentLayerParameterName='driver'))
        self.addParameter(QgsProcessingParameterFeatureSink('systematized_data', 
        'Systematized Data', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, 
        supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):

        use_concave = self.parameterAsBool(parameters, self.USE_CONCAVE, context)
        use_min_bounding = self.parameterAsBool(parameters, 'USE_MIN_BOUNDING', context)

        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
        results = {}
        outputs = {}

        if use_concave:
            # Implemente a lógica para Concave Hull
            valor_ajuste = self.parameterAsDouble(parameters, self.CONCAVE_PARAMETER, context)

            # Use QgsExpressionBuilderDialog para obter o campo de agrupamento dinamicamente
            field_aggreg = self.parameterAsString(parameters, 'field_aggreg', context)

            #camada_driver_candidato = self.parameterAsVectorLayer(parameters, 'driver', context) #nova
            if not field_aggreg:
                QMessageBox.critical(None, "Erro", "Grouping field selection canceled")
                return {}

            # Concave hull
            alg_params = {
                'ALPHA': parameters[self.CONCAVE_PARAMETER],
                'HOLES': True,
                'INPUT': parameters['layer_to_analysis'],
                'NO_MULTIGEOMETRY': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ConcaveHull'] = processing.run('qgis:concavehull', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}

            # Buffer
            alg_params = {
                'DISSOLVE': True,
                'DISTANCE': parameters['define_buffer'],
                'END_CAP_STYLE': 0,  # Round
                'INPUT': outputs['ConcaveHull']['OUTPUT'],
                'JOIN_STYLE': 0,  # Round
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'SEPARATE_DISJOINT': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}

            # Clip (corta camada drive pelo buffer da camada pontual) Concave hull
            alg_params = {
                'INPUT': parameters['driver'],
                'OVERLAY': outputs['Buffer']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['driver_clipped'] = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(3)
            if feedback.isCanceled():
                return {}

            # algoritmo de agregação
            alg_params = {
                'AGGREGATES': [{'aggregate': 'concatenate_unique', 'delimiter': ',', 'input': f'"{field_aggreg}"', 'length': 250,
                                'name': field_aggreg, 'precision': 0, 'sub_type': 0, 'type': 10, 'type_name': 'text'}],
                'GROUP_BY': f'"{field_aggreg}"',
                'INPUT': outputs['driver_clipped']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Aggregate'] = processing.run('native:aggregate', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
     
            feedback.setCurrentStep(4)
            if feedback.isCanceled():
                return {}

            # Count points in polygon
            alg_params = {
                'CLASSFIELD': '',
                'FIELD': 'NUMPOINTS',
                'POINTS': parameters['layer_to_analysis'],
                'POLYGONS': outputs['Aggregate']['OUTPUT'],
                'WEIGHT': '',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['CountPointsInPolygon'] = processing.run('native:countpointsinpolygon', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(5)
            if feedback.isCanceled():
                return {}

            # Field calculator: esperado
            alg_params = {
                'FIELD_LENGTH': 3,
                'FIELD_NAME': 'expected_vals',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,
                'FORMULA': '($area/sum($area))',
                'INPUT': outputs['CountPointsInPolygon']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculatorAreaporc'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(6)
            if feedback.isCanceled():
                return {}

            # Field calculator (observado)
            alg_params = {
                'FIELD_LENGTH': 3,
                'FIELD_NAME': 'observed_vals',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,
                'FORMULA': '"NUMPOINTS"/sum("NUMPOINTS")',
                'INPUT': outputs['FieldCalculatorAreaporc']['OUTPUT'],
                'OUTPUT': parameters['systematized_data']
            }
            outputs['FieldCalculatorObservado'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['systematized_data'] = outputs['FieldCalculatorObservado']['OUTPUT']
                        
        if use_min_bounding:
            min_bounding_type = self.parameterAsEnum(parameters, self.MIN_BOUNDING_TYPE, context)
            bounding_output = None

            # Use QgsExpressionBuilderDialog para obter o campo de agrupamento dinamicamente
            field_aggreg = self.parameterAsString(parameters, 'field_aggreg', context)
            #camada_driver_candidato = self.parameterAsVectorLayer(parameters, 'driver', context) #nova
            if not field_aggreg:
                QMessageBox.critical(None, "Erro", "Grouping field selection canceled")
                return {}

            if min_bounding_type == 0:  # 'Envelope (Caixa limitante)'
                # Lógica para Envelope
                alg_params = {
                    'INPUT': parameters['layer_to_analysis'],
                    'TYPE': 0,  # Envelope
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                bounding_output = processing.run('qgis:minimumboundinggeometry', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)['OUTPUT']

            elif min_bounding_type == 1:  # 'Retângulo Orientado Mínimo'
                # Lógica para Retângulo Orientado Mínimo
                alg_params = {
                    'INPUT': parameters['layer_to_analysis'],
                    'TYPE': 1,  # Retângulo Orientado Mínimo
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                bounding_output = processing.run('qgis:minimumboundinggeometry', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)['OUTPUT']

            elif min_bounding_type == 2:  # 'Círculo Fechado Mínimo'
                # Lógica para Círculo Fechado Mínimo
                alg_params = {
                    'INPUT': parameters['layer_to_analysis'],
                    'TYPE': 2,  # Círculo Fechado Mínimo
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                bounding_output = processing.run('qgis:minimumboundinggeometry', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)['OUTPUT']

            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}
                
            # Buffer
            alg_params = {
                'DISSOLVE': True,
                'DISTANCE': parameters['define_buffer'],
                'END_CAP_STYLE': 0,  # Round
                'INPUT': bounding_output,  # Usa a saída do processo de MIN_BOUNDING
                'JOIN_STYLE': 0,  # Round
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'SEPARATE_DISJOINT': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)

            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}

            # Clip (corta camada drive pelo buffer da camada pontual)
            alg_params = {
                'INPUT': parameters['driver'],
                'OVERLAY': outputs['Buffer']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['driver_clipped'] = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(3)
            if feedback.isCanceled():
                return {}

            # algoritmo de agregação
            alg_params = {
                'AGGREGATES': [{'aggregate': 'concatenate_unique', 'delimiter': ',', 'input': f'"{field_aggreg}"', 'length': 250,
                                'name': field_aggreg, 'precision': 0, 'sub_type': 0, 'type': 10, 'type_name': 'text'}],
                'GROUP_BY': f'"{field_aggreg}"',
                'INPUT': outputs['driver_clipped']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Aggregate'] = processing.run('native:aggregate', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
     
            feedback.setCurrentStep(4)
            if feedback.isCanceled():
                return {}

            # Count points in polygon
            alg_params = {
                'CLASSFIELD': '',
                'FIELD': 'NUMPOINTS',
                'POINTS': parameters['layer_to_analysis'],
                'POLYGONS': outputs['Aggregate']['OUTPUT'],
                'WEIGHT': '',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['CountPointsInPolygon'] = processing.run('native:countpointsinpolygon', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(5)
            if feedback.isCanceled():
                return {}

            # Field calculator: esperado
            alg_params = {
                'FIELD_LENGTH': 3,
                'FIELD_NAME': 'expected_vals',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,  # Decimal (double)
                'FORMULA': '($area/sum($area))',
                'INPUT': outputs['CountPointsInPolygon']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculatorAreaporc'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(6)
            if feedback.isCanceled():
                return {}

            # Field calculator (observado)
            alg_params = {
                'FIELD_LENGTH': 3,
                'FIELD_NAME': 'observed_vals',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,
                'FORMULA': '"NUMPOINTS"/sum("NUMPOINTS")',
                'INPUT': outputs['FieldCalculatorAreaporc']['OUTPUT'],
                'OUTPUT': parameters['systematized_data']
            }
            outputs['FieldCalculatorObservado'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['systematized_data'] = outputs['FieldCalculatorObservado']['OUTPUT']
  
        return results

    def name(self):
        return 'Spatial_Randomness_Test_p1'

    def displayName(self):
        return 'Spatial Randomness Part 1: Overlay process and data preparation'

    def group(self):
        return 'Randomness Point Pattern Test (RPPT)'

    def groupId(self):
        return 'Randomness Point Pattern Test (RPPT)'

    def createInstance(self):
        return AleatorioProcessingAlgorithm()


    def shortHelpString(self):

        return (
            "<font size='4' face='Arial'><b>Abstract\
            \n  \
            \n                                                    \
            \n \
            \n Analyzes whether the observed point pattern is driven by another spatial component (polygon). If the specific spatial pattern is driven by some spatial component, the observed point pattern isn´t random.\
            \n \
            \n Part1: prepare data to Part 2: Chi-square goodness-of-fit Test\
            \n \
            \n Attention: First of all, verify that the layers are in the same cartographic reference system (CRS), have valid geometry, and maintain topological consistency\
            \n \
            \n<font size='4' face='Arial'><b>                         Parameters                           \
            \n \
            \n <b>Layer to be analyzed (points) \
            \n    >     Vector layer containing the pattern to be analized: type point\
            \n >>> Use adjusted delimitation (Concave Hull): 0 is the most adjusted around points and 1 is equivalent with Convex Hull\
            \n \
            \n>> <font size='4' face='Arial'><b>OR (select only one type per processing)<b> <<\
            \n \
            \n >>> Minimum Bounding Geometry: Envelope (bounding box), Minimal oriented rectangle, Minimal enclosing circle\
            \n \
            \n <b>Driver - layer (Polygon) \
            \n >     Vector layer containing the theme to be analyzed, for example: Geology, LULC - Land Use and Land Cover, etc: type polygon\
            \n >>> Defines the width of the study area around the points: is a buffer that represent the influence area around points\
            \n \
            \n \
            \n contact: \
            \n tonysampaio@ufpr.br / tony2sampaio@gmail.com - LAPE-CT/UFPR/BRAZIL \
            \n jorge.rocha@edu.ulisboa.pt - GEOMODLAB/UL/PORTUGAL "
            )

            
    def helpUrl(self):
        """
        Returns the URL of the help online
        """
        return 'https://github.com/....'