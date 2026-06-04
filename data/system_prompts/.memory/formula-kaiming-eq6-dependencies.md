---
description: Prerequisite papers for Eq 6 of He et al. 2015 (Kaiming initialization
  forward variance product)
metadata:
  type: knowledge
name: formula-kaiming-eq6-dependencies
---

Equation 6 from "Delving Deep into Rectifiers" (He, Zhang, Ren, Sun, ICCV 2015, arXiv:1502.01852) is:

Var[y_L] = Var[y_1] × ∏_{l=2}^{L} (½ × n_l × Var[w_l])

This is the forward propagation variance product formula. It expresses how response variance propagates through L layers of a ReLU network, where each layer halves the variance due to ReLU's zeroing of negative values (hence the ½ factor), and n_l = k²c is the number of input connections per neuron.

Derivation chain:
- Eq (4): Var[y_l] = n_l Var[w_l] E[x_l^2] (Glorot & Bengio 2010 variance propagation methodology)
- ReLU property: E[x_l^2] = ½ Var[y_{l-1}] (because ReLU kills negative half of symmetric distribution — Nair & Hinton 2010)
- Eq (5): Var[y_l] = ½ n_l Var[w_l] Var[y_{l-1}]
- Eq (6): Var[y_L] = Var[y_1] ∏_{l=2}^{L} ½ n_l Var[w_l]
- Eq (7): ½ n_l Var[w_l] = 1 → σ = √(2/n_l) (Kaiming initialization)

Key prerequisite papers:
Level 1 (direct dependency):
- Glorot & Bengio 2010, "Understanding the difficulty of training deep feedforward neural networks", AISTATS 2010
Read: Section 4.2, equations (11)–(16) — the variance propagation methodology
He et al. explicitly states: "Our derivation mainly follows [Glorot2010]" (Sec. 2.2)

Level 2 (ReLU halving factor):
- Nair & Hinton 2010, "Rectified Linear Units Improve Restricted Boltzmann Machines", ICML 2010
Read: Sections 1–2 — ReLU definition and properties
Explains why E[x_l^2] = ½ Var[y_{l-1}] for symmetric y

- Glorot, Bordes & Bengio 2011, "Deep Sparse Rectifier Neural Networks", AISTATS 2011
Read: Section 2 — properties of ReLU networks and why they avoid vanishing gradients

Level 3 (foundational motivation):
- LeCun, Bottou, Orr & Müller 1998/2012, "Efficient BackProp"
Read: Section on "Initializing the Weights" — the principle of keeping signal variance ≈ 1

Symbols:
- Var[y_l]: variance of response at layer l
- n_l = k² × c_l: number of input connections (filter size² × input channels)
- Var[w_l]: variance of initialized weights at layer l
- ½: "ReLU halving factor"