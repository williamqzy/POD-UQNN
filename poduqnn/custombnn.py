"""Module with a class defining a Bayesian Neural Network."""

import os
import pickle
import tensorflow as tf
import tensorflow_probability as tfp
import numpy as np

tfk = tf.keras
K = tf.keras.backend
tfd = tfp.distributions

NORM_NONE = "none"
NORM_MEANSTD = "meanstd"
NORM_CENTER = "center"
NORM_MINMAX = "minmax"

tfk = tf.keras
K = tf.keras.backend
tfd = tfp.distributions


class BayesianNeuralNetwork:
    """Custom class defining a Bayesian Neural Network model."""
    def __init__(self, layers, lr, klw=1,
                 exact_kl=False, activation="relu",
                 pi_0=None, pi_1=None, pi_2=None, soft_0=0.01, adv_eps=None,
                 norm=NORM_NONE, weights_path=None, norm_bounds=None):
        # Making sure the dtype is consistent
        self.dtype = "float32"
        tf.keras.backend.set_floatx(self.dtype)

        # Setting up optimizer and params
        self.optimizer = tf.optimizers.Adam(learning_rate=lr)
        self.layers = layers
        self.lr = lr
        self.klw = klw
        self.norm_bounds = norm_bounds
        self.logger = None
        self.batch_size = 0
        self.norm = norm
        self.activation = activation
        self.exact_kl = exact_kl
        self.is_prior_trainable = pi_0 is None and pi_1 is None and pi_2 is None
        self.pi_0 = pi_0
        self.pi_1 = pi_1
        self.pi_2 = pi_2
        self.soft_0 = soft_0
        self.adv_eps = adv_eps

        # Setting up the model
        self.model = self.build_model()
        if weights_path is not None:
            self.model.load_weights(weights_path)

    def get_prior(self):
        if self.is_prior_trainable:
            print("Using trainable prior")
            # def prior_trainable(kernel_size, bias_size=0, dtype=None):
            #     n = kernel_size + bias_size
            #     c = np.log(np.expm1(1.))
            #     return tf.keras.Sequential([
            #         tfp.layers.VariableLayer(2 * n, dtype=dtype),
            #         tfp.layers.DistributionLambda(lambda t: tfd.Independent(
            #             tfd.Normal(loc=t[..., :n],
            #                         scale=1e-5 + tf.nn.softplus(c + t[..., n:])),
            #             reinterpreted_batch_ndims=1)),
            #     ])
            # def prior_trainable(kernel_size, bias_size=0, dtype=None):
            #     n = kernel_size + bias_size
            #     return tf.keras.Sequential([
            #         tfp.layers.VariableLayer(n, dtype=dtype),
            #         tfp.layers.DistributionLambda(lambda t: tfd.Independent(
            #             tfd.Normal(loc=t, scale=1),
            #             reinterpreted_batch_ndims=1)),
            #     ])
            def prior_trainable(kernel_size, bias_size=0, dtype=None):
                n = kernel_size + bias_size
                return tf.keras.Sequential([
                    tfp.layers.VariableLayer(n, dtype=dtype),
                    tfp.layers.DistributionLambda(lambda t: tfd.Independent(
                        tfd.Normal(loc=tf.zeros_like(t), scale=t),
                        reinterpreted_batch_ndims=1)),
                ])
            return prior_trainable

        print(f"Using fixed mixture prior with " + 
                f"pi_0={self.pi_0}, pi_1={self.pi_1}, pi_2={self.pi_2}")
        def mixture_prior(kernel_size, bias_size=0, dtype=None):
            n = kernel_size + bias_size
            pi_0 = tf.cast(self.pi_0, dtype=dtype)
            pi_1 = tf.cast(self.pi_1, dtype=dtype)
            pi_2 = tf.cast(self.pi_2, dtype=dtype)
            return tf.keras.Sequential([
                tfp.layers.VariableLayer(n, dtype=dtype, trainable=False, initializer="zeros"),
                tfp.layers.DistributionLambda(lambda t:
                    tfd.Mixture(
                    cat=tfd.Categorical(probs=[pi_0, 1. - pi_0]),
                    components=[
                        tfd.Independent(
                            tfd.Normal(loc=t, scale=pi_1),
                            reinterpreted_batch_ndims=1),
                        tfd.Independent(
                            tfd.Normal(loc=t, scale=pi_2),
                            reinterpreted_batch_ndims=1),
                    ]),)
            ])
        return mixture_prior

    def get_posterior(self):
        pi_0 = self.pi_0 or 0.5
        pi_1 = self.pi_1 or 1.5
        pi_2 = self.pi_2 or 0.1
        init_sig = np.sqrt(pi_0 * pi_1**2 + (1-pi_0) * pi_2**2)

        def _initializer(shape, dtype=None, partition_info=None):
            n = int(shape / 2)
            x = K.random_normal((n,), stddev=init_sig, dtype=dtype)
            y = K.zeros((n,), dtype=dtype)
            return tf.concat([x, y], 0)

        def posterior_mean_field(kernel_size, bias_size=0, dtype=None):
            n = kernel_size + bias_size
            c = np.log(np.expm1(1.))
            return tf.keras.Sequential([
                tfp.layers.VariableLayer(2 * n, dtype=dtype,
                    initializer=lambda shape, dtype: _initializer(shape, dtype=dtype)),
                tfp.layers.DistributionLambda(lambda t: tfd.Independent(
                    tfd.Normal(loc=t[..., :n],
                                scale=1e-5 + tf.nn.softplus(c + t[..., n:])),
                    reinterpreted_batch_ndims=1)),
            ])
        return posterior_mean_field

    def build_model(self):
        """Functional Keras model."""
        prior = self.get_prior()
        posterior = self.get_posterior()

        # Defining the model
        inputs = tf.keras.Input(shape=(self.layers[0],), name="x", dtype=self.dtype)

        x = inputs
        for width in self.layers[1:-1]:
            x = tfp.layers.DenseVariational(
                    width, posterior, prior,
                    activation=self.activation, dtype=self.dtype,
                    kl_weight=self.klw, kl_use_exact=self.exact_kl)(x)
        x = tfp.layers.DenseVariational(
                2 * self.layers[-1], posterior, prior,
                activation=None, dtype=self.dtype,
                kl_weight=self.klw)(x)

        outputs = tfp.layers.DistributionLambda(
            lambda t: tfd.Normal(loc=t[..., :self.layers[-1]],
                scale=tf.math.softplus(self.soft_0 * t[..., self.layers[-1]:]) + 1e-4),
        )(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs, name="bnn")
        return model

    @tf.function
    def grad(self, X, y):
        """Compute the loss and its derivatives w.r.t. the inputs."""
        with tf.GradientTape(persistent=True) as tape:
            tape.watch(X)
            y_pred = self.model(X)
            loss_value = tf.reduce_sum(-y_pred.log_prob(y))
            loss_value += tf.reduce_sum(self.model.losses)
            if self.adv_eps is not None:
                loss_x = tape.gradient(loss_value, X)
                X_adv = X + self.adv_eps * tf.math.sign(loss_x)
                y_adv_pred = self.model(X_adv)
                loss_value += tf.reduce_sum(-y_adv_pred.log_prob(y))
        grads = tape.gradient(loss_value, self.wrap_trainable_variables())
        del tape
        return loss_value, grads

    def wrap_trainable_variables(self):
        """Wrapper of all trainable variables."""
        return self.model.trainable_variables

    def set_normalize_bounds(self, X):
        """Setting the normalization bounds, according to the chosen method."""
        if self.norm == NORM_CENTER or self.norm == NORM_MINMAX:
            lb = X.min(0)
            ub = X.max(0)
            self.norm_bounds = (lb, ub)
        elif self.norm == NORM_MEANSTD:
            lb = X.mean(0)
            ub = X.std(0)
            self.norm_bounds = (lb, ub)

    def normalize(self, X):
        """Perform the normalization on the inputs."""
        if self.norm_bounds is None:
            return self.tensor(X)
        if self.norm == NORM_CENTER:
            lb, ub = self.norm_bounds
            X = (X - lb) - 0.5 * (ub - lb)
        elif self.norm == NORM_MEANSTD:
            mean, std = self.norm_bounds
            X = (X - mean) / std
        return self.tensor(X)

    def fit(self, X_v, v, epochs, logger=None):
        """Train the model over a given dataset, and parameters."""
        # Setting up logger
        self.logger = logger
        if self.logger is not None:
            self.logger.log_train_start()

        # Normalizing and preparing inputs
        self.set_normalize_bounds(X_v)
        X_v = self.normalize(X_v)
        v = self.tensor(v)

        # Optimizing
        for e in range(epochs):
            loss_value, grads = self.grad(X_v, v)
            self.optimizer.apply_gradients(
                zip(grads, self.wrap_trainable_variables()))
            if self.logger is not None:
                self.logger.log_train_epoch(e, loss_value)

        if self.logger is not None:
            self.logger.log_train_end(epochs, tf.constant(0., dtype=self.dtype))

    def predict_dist(self, X):
        """Get the prediction distribution for a new input X."""
        X = self.normalize(X)
        return self.model(X)

    def predict(self, X, samples=5):
        """Get the prediction for a new input X."""
        X = self.normalize(X)
        v_pred_samples = np.zeros((samples, X.shape[0], self.layers[-1]))
        v_pred_var_samples = np.zeros((samples, X.shape[0], self.layers[-1]))

        for i in range(samples):
            v_dist = self.model(X)
            v_pred, v_pred_var = v_dist.mean(), v_dist.variance()
            v_pred_samples[i] = v_pred.numpy()
            v_pred_var_samples[i] = v_pred_var.numpy()

        # Approximate the mixture in a single Gaussian distribution
        v_pred = v_pred_samples.mean(0)
        v_pred_var = (v_pred_var_samples + v_pred_samples ** 2).mean(0) - v_pred ** 2
        return v_pred, v_pred_var

    def summary(self):
        """Print a summary of the TensorFlow/Keras model."""
        return self.model.summary()

    def tensor(self, X):
        """Convert input into a TensorFlow Tensor with the class dtype."""
        return tf.convert_to_tensor(X, dtype=self.dtype)

    def save_to(self, model_path, params_path):
        """Save the (trained) model and params for later use."""
        with open(params_path, "wb") as f:
            pickle.dump((self.layers, self.lr, self.klw, self.exact_kl, self.activation,
                         self.pi_0, self.pi_1, self.pi_2,
                         self.norm, self.norm_bounds), f)
        self.model.save_weights(model_path)

    @classmethod
    def load_from(cls, model_path, params_path):
        """Load a (trained) model and params."""
        if not os.path.exists(params_path):
            raise FileNotFoundError("Can't find cached model params.")

        with open(params_path, "rb") as f:
            layers, lr, klw, exact_kl, activation, pi_0, pi_1, pi_2, norm, norm_bounds = pickle.load(f)
        print(f"Loading model params from {params_path}")
        return cls(layers, lr, klw, exact_kl, activation,
                   pi_0, pi_1, pi_2,
                   weights_path=model_path, norm=norm, norm_bounds=norm_bounds)