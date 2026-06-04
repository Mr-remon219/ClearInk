---
description: Step-by-step derivation trace of Equation 6 from the extracted LaTeX
  source of He et al. 2015
metadata:
  type: reference
name: kaiming-eq6-derivation-details
---

From the LaTeX source of He et al. (arXiv:1502.01852, prelu.tex, Section 2.2 "Initialization of Filter Weights for Rectifiers"):

Forward propagation case derivation (lines 226–260):

1. Layer response: y_l = W_l x_l + b_l
- x_l is a k²c-by-1 vector (co-located k×k pixels in c input channels)
- n = k²c denotes the number of connections of a response
- x_l = f(y_{l-1}) where f is the activation (ReLU)

2. Key assumptions (following Glorot & Bengio 2010):
- Elements in W_l are mutually independent, same distribution
- Elements in x_l are mutually independent, same distribution
- x_l and W_l are independent
- w_l has zero mean

3. Variance of product of independent variables (Eq 4):
Var[y_l] = n_l Var[w_l] E[x_l^2]

4. For ReLU activation (x_l = max(0, y_{l-1})):
- If w_{l-1} has symmetric distribution around zero and b_{l-1}=0,
then y_{l-1} has zero mean and symmetric distribution around zero
- This gives: E[x_l^2] = ½ Var[y_{l-1}]

5. Substituting (Eq 5):
Var[y_l] = ½ n_l Var[w_l] Var[y_{l-1}]

6. Chaining L layers (Eq 6):
Var[y_L] = Var[y_1] × ∏_{l=2}^{L} (½ × n_l × Var[w_l])

7. Sufficient condition to avoid exponential scaling (Eq 7):
½ n_l Var[w_l] = 1, ∀l
→ std = √(2/n_l) for zero-mean Gaussian

Backward propagation case (lines 265–293) yields an analogous condition:
½ × ĥ_n_l × Var[w_l] = 1
where ĥ_n_l = k_l² × d_l (number of output connections)

Note: The derivation is an extension of Glorot & Bengio 2010 where n_l Var[w_l] = 1 (for linear case). The ½ factor is the key addition for ReLU nonlinearity.