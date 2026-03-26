# Rosetta Zero: Sovereign Agentic Refactoring Engine

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Rust Engine](https://img.shields.io/badge/Engine-Rust-DEA584?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Infrastructure: AWS CDK](https://img.shields.io/badge/Infrastructure-AWS%20CDK-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/cdk/)

**Rosetta Zero** is a deterministic, agentic framework engineered to refactor legacy binary logic and monolithic codebases into verified, cloud-native serverless functions. By leveraging a **Double-Blind Verification** protocol, Rosetta ensures $1:1$ logic parity while transitioning mission-critical infrastructure to modern, memory-safe environments.

---

## Architecture

Rosetta operates on the principle of **Sovereign AI**: all processing is designed for local edge deployment or VPC-isolated environments, ensuring data localization and strict regulatory compliance.

### The Four-Stage Logic Loop
1.  **Decompilation & Lifting:** Extraction of raw logic from legacy binaries into a high-level Intermediate Representation (IR).
2.  **Synthesis Engine:** A Rust-driven core that generates equivalent AWS Lambda functions, prioritizing memory safety and execution efficiency.
3.  **Double-Blind Verification:** Two independent Agentic Evaluators—the **Prover** and the **Verifier**—execute symbolic comparisons between the source and target logic to eliminate drift.
4.  **Truth Injection:** Deterministic mathematical constraints are injected into the unit testing suite to prevent "hallucinated" logic outcomes and ensure formal correctness.

---
##  Media & Documentation

* **Watch the Demo:** [Rosetta Zero Project Overview](https://www.youtube.com/watch?v=sF9rYg3IRO8)
* **Technical Deep Dive:** [AWS Community Builder: Rosetta Zero Case Study](https://builder.aws.com/content/3AaK0aYSsVfpbdMnkn8A7mZBOdE/aideas-rosetta-zero)

---

## 📂 Project Structure

```text
rosetta/
├── src/
│   ├── rosetta_zero/       # Core refactoring engine & logic
│   ├── orchestrator.py     # Main Agentic workflow manager
│   └── encoders/           # Custom Rust-based binary parsers
├── infrastructure/         # AWS CDK (TypeScript/Python) for Cloud-Native deployment
├── tests/                  # Deterministic test suites (Hypothesis-driven)
├── docker/                 # Containerized execution environments for legacy isolation
├── Makefile                # Unified build and deployment interface
└── pyproject.toml          # Modern dependency management
```
---

## Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Orchestration** | AWS Step Functions | Managing the Double-Blind Verification state machine. |
| **Logic Synthesis** | Amazon Bedrock (Claude 3.5 Sonnet) | Structural de-monolithization and reasoning. |
| **Contextual Memory** | Amazon Titan Text Embeddings v2 | Indexing legacy documentation and architectural patterns. |
| **Execution Layer** | AWS Lambda | Event-driven compute for refactored modular logic. |
| **Binary Parsing** | Rust | High-performance, memory-safe legacy binary ingestion. |
| **Infrastructure** | AWS CDK (v2) | Defining Sovereign AI environments as code. |
| **Immutable Ledger** | Amazon S3 (Object Lock) | Storing tamper-proof Certificates of Behavioral Equivalence. |
| **Development** | Kiro | Spec-driven development of core synthesis engines. |

---

 ## Key Features
 
Agentic Parity Check: Moves beyond simple syntax conversion by verifying the behavioral state of the refactored code.

Sovereign Compliance: Designed for national digital infrastructure, prioritizing data localization and local model execution.

Serverless First: Automatically converts legacy stateful logic into stateless, scalable AWS Lambda functions.

Symbolic Execution: Uses formal verification methods to ensure that the refactored logic handles edge cases exactly like the original system.

---

### Installation & Setup

#### Prerequisites
```text
Python 3.11+
AWS CLI & CDK (Authenticated)
Docker Desktop (for local legacy execution)
Rust Toolchain (for the synthesis engine)
```

### Quick Start

Bash
```text
# Clone the repository
git clone https://github.com/niy-ati/rosetta.git
cd rosetta

# Install dependencies using the unified Makefile
make install

# Run the local verification suite
make test
```
---

## 🛡 Security & Sovereign Policy
Rosetta Zero is built with a Zero-Trust approach to AI integration:

Local Inference: Supports local LLM execution (via vLLM or Ollama) to prevent data leakage to third-party providers.

Isolated Execution: Legacy binaries are executed within hardened Docker containers to prevent unauthorized system calls during the lifting phase.

Auditability: Every refactoring decision made by the agentic loop is logged with a mathematical proof of parity.

---

## Contributors & Mentorship
Core Engineer: [Niyati Jain]

---
📜 License
This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
