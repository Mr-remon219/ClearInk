---
description: Annotated reading order and section-level prerequisites for fully understanding
  Equation 6 of He et al. 2015 (Kaiming initialization)
metadata:
  type: knowledge
name: kaiming-eq6-prerequisite-reading-list
---

# Prerequisite Reading Order for Kaiming Eq 6

## The Formula
Var[y_L] = Var[y_1] · ∏_{l=2}^{L} (½ · n_l · Var[w_l])

This is the forward propagation variance product for a ReLU network. The sufficient condition ½·n_l·Var[w_l] = 1 yields σ = √(2/n_l).

## Components
- ½: ReLU halving factor (zeros out negative half of symmetric distribution)
- n_l = k²·c_l: number of input connections per neuron (filter area × input channels)
- Var[w_l]: variance of initialized weights at layer l

## Recommended Reading Order with Section-Level Guidance

### Step 1: Foundational motivation — LeCun, Bottou, Orr & Müller (1998/2012)
**Paper:** "Efficient BackProp" in Neural Networks: Tricks of the Trade
**Read:** Section "Initializing the Weights" — why variance ≈ 1 through layers prevents vanishing/exploding signals
**Purpose:** Understand why variance control matters at all

### Step 2: Mathematical machinery — Glorot & Bengio (2010)
**Paper:** "Understanding the difficulty of training deep feedforward neural networks", AISTATS 2010
**Read:** Section 4.2, Equations (11)–(16)
**Purpose:** Direct dependency — He et al. explicitly say "Our derivation mainly follows [Glorot2010]".
Eq (4) of He paper comes from here: Var[y_l] = n_l Var[w_l] E[x_l²]
Key assumptions: independent weights, independent inputs, zero-mean w_l

### Step 3: ReLU halving factor — Nair & Hinton (2010)
**Paper:** "Rectified Linear Units Improve Restricted Boltzmann Machines", ICML 2010
**Read:** Sections 1–2 — ReLU definition max(0,x) and why E[x²] = ½Var[y] for symmetric zero-mean y
**Purpose:** Explains the ½ factor that converts Eq (4) → Eq (5)

### Step 4: ReLU context — Glorot, Bordes & Bengio (2011)
**Paper:** "Deep Sparse Rectifier Neural Networks", AISTATS 2011
**Read:** Section 2 — properties of ReLU networks, sparsity, vanishing gradient avoidance
**Purpose:** Provides broader motivation for designing initialization specifically for ReLU

### Step 5: Return to target — He et al. (2015)
**Paper:** "Delving Deep into Rectifiers: Surpassing Human-Level Performance on ImageNet Classification", ICCV 2015
**Read:** Section 2.2 "Initialization of Filter Weights for Rectifiers"
**Now the derivation is transparent**

## Derivation Chain
Eq (4): Var[y_l] = n_l Var[w_l] E[x_l²]                                 ← Glorot & Bengio 2010
↓  E[x_l²] = ½ Var[y_{l-1}]                                        ← Nair & Hinton 2010 (ReLU property)
Eq (5): Var[y_l] = ½ n_l Var[w_l] Var[y_{l-1}]
↓  Unroll recursively
Eq (6): Var[y_L] = Var[y_1] × ∏_{l=2}^{L} (½ n_l Var[w_l])
↓  Set product term = 1
Eq (7): ½ n_l Var[w_l] = 1  →  σ = √(2/n_l)                            ← Kaiming initialization

## Note on Metadata Verification
The scholar CLI (google-scholar-cli) was unavailable in this environment. All citations rely on previously stored memory (formula-kaiming-eq6-dependencies.md) rather than live BibTeX verification. For production use, run `scholar lookup --bibtex` on each title to obtain verified metadata.