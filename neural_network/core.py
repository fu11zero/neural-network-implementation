"""
The core contains the definition of the perceptron class and the layer class
"""
from __future__ import annotations
import numpy as np
from typing import Callable, List, Union, Optional

from neural_network.activation_functions import ActivationFunction
from neural_network.utils import convert_to_vector, make_batches, make_normalization_function, mse, pairwise, shuffle_


class Dense:
    """
    Fully-connected layer of neurons
    """

    def __init__(self,
                 neurons: int,
                 activation_function: Union[str, ActivationFunction, None] = None,
                 use_bias: bool = False):
        if not isinstance(neurons, int):
            raise TypeError(f"The number of neurons must be a positive integer, not {type(neurons).__name__}")
        if neurons < 0:
            raise ValueError("The number of neurons must be a positive integer, not negative")

        if activation_function is None:
            self.__activation_function = None
        elif isinstance(activation_function, ActivationFunction):
            self.__activation_function = activation_function
        elif isinstance(activation_function, str):
            self.__activation_function = ActivationFunction.get_by_name(activation_function)
        else:
            raise TypeError(f"Activation function must be [None, str, ActivationFunction], "
                            f"not {type(activation_function).__name__}")

        self.__neurons = neurons
        self.weights = None
        self.use_bias = use_bias

        self.input = None
        self.__output = None
        self.__error = None

    def initialize_weights(self, next_layer_neurons: int) -> None:
        """
        Initialising a matrix of weights with a normal distribution

        :param next_layer_neurons: Number of neurons on the next layer
        """
        matrix_size = (next_layer_neurons, self.neurons + 1) if self.use_bias else (next_layer_neurons, self.neurons)
        self.weights = np.random.normal(loc=0.0, scale=pow(matrix_size[1], -0.5), size=matrix_size)

    def is_first(self) -> bool:
        """
         Checks if this is the first layer.

        The first layer has no activation function (and input)
        """
        return self.activation_function is None

    def is_last(self) -> bool:
        """
        Checks if this is the last layer.

        The last layer has no weights
        """
        return self.weights is None

    @property
    def neurons(self) -> int:
        """
        The number of neurons on this layer (without bias anyway)
        """
        return self.__neurons

    @property
    def activation_function(self) -> Optional[ActivationFunction]:
        """
        Layer activation function
        """
        return self.__activation_function

    @property
    def output(self) -> np.ndarray:
        """
        Input after activation function
        """
        return self.__output

    @output.setter
    def output(self, value):
        if self.use_bias:  # Bias is added for use on the next layer
            self.__output = np.vstack((value, 1))
        else:
            self.__output = value

    @property
    def error(self) -> np.ndarray:
        """
        Just error used for backpropagation algorithm
        """
        if self.use_bias:  # The error for bias is removed to correctly update the weights on the previous layer
            return self.__error[:-1, :]
        return self.__error

    @error.setter
    def error(self, value):
        self.__error = value

    def __repr__(self):
        activation_function_name = self.activation_function.name if not self.is_first() else None
        return f"Fully-connected layer [" \
               f"neurons = {self.neurons}, " \
               f"use_bias = {self.use_bias}, " \
               f"First layer? = {self.is_first()}, " \
               f"Last layer? = {self.is_last()}, " \
               f"activation function = {activation_function_name}" \
               f"]"


# Some constants for neural networks
MINIMUM_LAYER_COUNT = 2
FIRST_LAYER = 0
LAST_LAYER = -1


class Perceptron:
    """
    Multilayer perceptron class
    """
    normalize: Optional[Callable]
    learning_rate: float
    layers: List[Dense]
    mse_by_epoch: List[float]

    def __init__(self, layers: List[Dense], learning_rate: float):

        if len(layers) < MINIMUM_LAYER_COUNT:
            raise ValueError("The minimum allowable number of layers is "
                             f"{MINIMUM_LAYER_COUNT}. You passed on: {len(layers)}")
        if layers[FIRST_LAYER].activation_function is not None:
            raise Warning("The input layer does not need the activation function")
        if layers[LAST_LAYER].use_bias is True:
            raise Warning("The last layer does not need bias!")

        if not 0 < learning_rate <= 1:
            raise ValueError(f"Learning rate must be within (0, 1], not {learning_rate}")

        self.normalize = None
        self.mse_by_epoch = []
        self.learning_rate = learning_rate
        self.layers = layers

        for layer, next_layer in pairwise(layers):
            layer.initialize_weights(next_layer.neurons)

    def __query(self, data):
        """
        The transmitted data passes through the entire network to get response
        """
        self.layers[FIRST_LAYER].output = data

        for layer, next_layer in pairwise(self.layers):
            next_layer.input = layer.weights @ layer.output
            next_layer.output = next_layer.activation_function.f(next_layer.input)

        return self.layers[LAST_LAYER].output

    def __backpropagation(self, errors, batch_size: int) -> None:
        """
        Changing weights using backpropagation algorithm

        :param errors: Neural network errors in the last 'batch_size' trainings
        :param batch_size: Batch size
        """
        mean_error = sum(errors) / batch_size
        self.layers[LAST_LAYER].error = mean_error

        for next_layer, layer in pairwise(reversed(self.layers)):
            layer.error = layer.weights.T @ next_layer.error
            gradient = (next_layer.error * next_layer.activation_function.df(next_layer.input)) @ layer.output.T
            layer.weights += self.learning_rate * gradient

    def train(self,
              inputs,
              outputs,
              batch_size: int = 10,
              epochs: int = 5,
              shuffle: bool = True,
              normalize: bool = True,
              scope=(0, 1)):
        """
        Neural network training

        :param inputs: List of lists or 2d-numpy-array with input data

        :param outputs: List of lists or 2d-numpy-array with expected output

        :param batch_size: Number of training sessions in one batch

        :param epochs: The number of full passes of the transmitted data through the neural network

        :param shuffle: Whether to shuffle data between epochs

        :param normalize: Whether to normalize the data

        :param scope: Data normalisation range, used only with param normalize=True
        """
        if len(inputs) != len(outputs):
            raise ValueError(f"The input data length {len(inputs)} must be "
                             f"equal to the output data length {len(outputs)} !")

        for index, input_ in enumerate(inputs):
            if len(input_) == self.layers[FIRST_LAYER].neurons:
                continue
            raise ValueError(f"Input data '{input_}' (at index {index}) contain not enough data! "
                             f"Its length must be equal to the number of neurons on the input layer")

        for index, output in enumerate(outputs):
            if len(output) == self.layers[LAST_LAYER].neurons:
                continue
            raise ValueError(f"Output data '{output}' (at index {index}) contain not enough data! "
                             f"Its length must be equal to the number of neurons on the output layer")

        training_dataset = np.array(inputs)
        expected_outputs = np.array(outputs)

        if normalize is True:
            min_value = training_dataset.min()
            max_value = training_dataset.max()
            self.normalize = make_normalization_function(min_value, max_value, scope=scope)
            training_dataset = self.normalize(training_dataset)

        for _ in range(epochs):
            if shuffle is True:
                training_dataset, expected_outputs = shuffle_(training_dataset, expected_outputs)

            batches = make_batches(training_dataset, batch_size), make_batches(expected_outputs, batch_size)

            actual = expected = None
            for batch in zip(*batches):
                errors = []
                for data, expected in zip(*batch):
                    actual = self.__query(convert_to_vector(data))
                    expected = convert_to_vector(expected)
                    errors.append(expected - actual)
                self.__backpropagation(errors, batch_size)
            self.mse_by_epoch.append(mse(expected, actual))

    def predict(self, data) -> List[float]:
        """
        Get a neural network response

        :param data: List with input data
        :return: List with output data
        """
        if len(data) != self.layers[FIRST_LAYER].neurons:
            raise ValueError(f"The number of incoming data ({len(data)}) does not correspond "
                             f"to the number of input neurons ({self.layers[FIRST_LAYER].neurons})!")

        data = convert_to_vector(data)

        if self.normalize is not None:
            data = self.normalize(data)

        response = self.__query(data)  # The response returns as a two-dimensional numpy array
        return response.flatten().tolist()
