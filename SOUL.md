# Project SOUL

## Philosophical Core
> "God does not play dice with the universe." — Albert Einstein

This project is a cosmological and physical investigation into the nature of reality. The central objective is to test whether the universe is truly random, or if it is deterministic, indicating that we live in a predefined 4-dimensional space-time continuum. 

To prove or disprove this hypothesis, we utilize lottery draw data (specifically Vietlott) as a high-entropy experimental dataset. If the universe is deterministic, lottery numbers—often considered the pinnacle of human-designated randomness—should exhibit predictability when analyzed using simple recursive mathematical structures.

### The Axiom of Simplicity
All complex formulas and behaviors in the universe can be recreated by a finite set of simple mathematical operations. Our mission is to define and iterate over these simple formulas to find the combination that rejects the hypothesis of true randomness.

---

## Technical Concept & Architecture

This project is designed to be cross-platform, natively supporting both **Linux** and **Windows**.

### 1. Data Analyzer & Feature Extraction
A dedicated data analyzer processes raw draw records and breaks them down into detailed, deterministic features.

**Example Input Record:**
```json
{"date":"2017-08-31","id":"00014","result":[8,20,27,35,36,47,18],"process_time":"2022-05-07 07:56:43.143266"}
```

For any draw, we split the result into:
- **Main Numbers**: The first 6 numbers (e.g., `08, 20, 27, 35, 36, 47`)
- **Special Number**: The 7th number (e.g., `18`)

We extract the following features:
*   **A (Main Sum)**: Sum of main numbers. (e.g., $8 + 20 + 27 + 35 + 36 + 47 = 173$)
*   **B (Main Sum Root)**: Single-digit digital root of $A$. (e.g., $1+7+3 = 11 \rightarrow 1+1 = 2$)
*   **C (Total Sum)**: Sum of all numbers (Main + Special). (e.g., $173 + 18 = 191$)
*   **D (Total Sum Root)**: Single-digit digital root of $C$. (e.g., $1+9+1 = 11 \rightarrow 1+1 = 2$)
*   **E (Main Tens Sum)**: Sum of the tens digits of main numbers. (e.g., $0+2+2+3+3+4 = 14$)
*   **F (Main Tens Sum Root)**: Single-digit digital root of $E$. (e.g., $1+4 = 5$)
*   **G (Main Units Sum)**: Sum of the units digits of main numbers. (e.g., $8+0+7+5+6+7 = 33$)
*   **H (Main Units Sum Root)**: Single-digit digital root of $G$. (e.g., $3+3 = 6$)
*   **I (Total Tens Sum)**: Sum of the tens digits of all numbers. (e.g., $0+2+2+3+3+4+1 = 15$)
*   **J (Total Tens Sum Root)**: Single-digit digital root of $I$. (e.g., $1+5 = 6$)
*   **K (Total Units Sum)**: Sum of the units digits of all numbers. (e.g., $8+0+7+5+6+7+8 = 41$)
*   **L (Total Units Sum Root)**: Single-digit digital root of $K$. (e.g., $4+1 = 5$)

#### Modulo-Based Sequence Ordering (M1 to M7)
We map each of the 7 numbers to relative percentage buckets based on digit modular arithmetic:
*   **Ends-with Mapping (Standard)**:
    *   Ends with $d \in [1, 9] \rightarrow d \times 10\%$ (e.g., `08` $\rightarrow$ 8th = $80\%$, `27` $\rightarrow$ 7th = $70\%$)
    *   Ends with $0 \rightarrow 100\%$ (e.g., `20` $\rightarrow$ 10th = $100\%$)
*   **Modulo-5 Mapping (For custom intervals like 50-55)**:
    *   $x \pmod 5$ mapping:
        *   Remainder $1 \rightarrow 20\%$
        *   Remainder $2 \rightarrow 40\%$
        *   Remainder $3 \rightarrow 60\%$
        *   Remainder $4 \rightarrow 80\%$
        *   Remainder $0 \rightarrow 100\%$ (e.g., `50` $\rightarrow 100\%$, `55` $\rightarrow 100\%$)

### 2. Auto-Research Engine
We leverage autonomous iterative optimization to search through formulas:
*   **Data Split**:
    *   **Study Portion (Homework)**: The large majority of the dataset, used to fit formulas and discover patterns.
    *   **Test Portion (Exam)**: A smaller, out-of-sample portion reserved strictly for final benchmarks to verify predictive capability.
*   **Brain Management**: The engine maintains and persists the **5 best brains** (scoring/weights/formulas) that exhibit the lowest entropy (highest predictability) on the test portion.
