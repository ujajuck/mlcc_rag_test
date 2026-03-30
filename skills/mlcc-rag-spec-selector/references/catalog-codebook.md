# Catalog Codebook

Use this reference when mapping user constraints to SEMCO MLCC catalog concepts and chunk targets.

## Contents

- Source Scope
- Truth Policy
- Chunk Routing
- Input Normalization
- Core Code Maps
- Capacitance Code and Nominal Rules
- Reliability and Family Routing
- Part-Number Skeleton Policy
- Active Lineup Pattern Policy
- Catalog Anomalies

## Source Scope

- Samsung Electro-Mechanics MLCC catalog
- Part I: Commercial / Industrial
- Primary project assets:
  - `MLCC_2512 .pdf`
  - `mlcc_catalog_rag_chunks.jsonl`
  - `mlcc_catalog_rag_master_ko.md`

## Truth Policy

Treat these as catalog-confirmable:

- 온도특성 코드 의미
- rated-voltage code meaning
- capacitance-code rule
- capacitance-tolerance code meaning
- size-code meaning
- thickness-code filtering
- reliability family descriptions
- example parts that appear directly in retrieved chunks

Treat these as validation-only unless directly retrieved for the target part:

- effective capacitance under 1V DC bias
- high-frequency effective capacitance
- exact ESR or ESL
- exact full 8th-11th codes
- exact orderable lineup or stocking status

Treat `caution_characteristics` graphs as sample guidance only.

## Chunk Routing

- `MLCC-002` to `MLCC-004`: part numbering, size, 온도특성 코드, capacitance code, tolerance, voltage, thickness, design, control, packaging
- `MLCC-005`: reliability-level comparison
- `MLCC-006` to `MLCC-012`: product families
- `MLCC-013` to `MLCC-014`: new-product example parts
- `MLCC-020` to `MLCC-021`: DC bias, AC voltage, impedance, aging, and caution characteristics
- `MLCC-031` to `MLCC-032`: operating conditions, storage, disclaimers

## Input Normalization

### Length

- Convert `um` to `mm`
- Example: `690 um -> 0.690 mm`

### Capacitance

- Normalize `uF`, `μF`, and `㎌` to `uF`
- When the requested nominal is off E-series, keep the target value and derive nearest standard options
- Example: `4.8 uF -> nearest standard around target: 4.7 uF (475), 5.1 uF (515)`

### Voltage

- Normalize `4V`, `4.0V`, `4Vdc` to `4.0Vdc`

### Tolerance

- `J = +/-5%`
- `K = +/-10%`
- `M = +/-20%`
- `Z = -20,+80%`

### Temperature Characteristic

카탈로그 원문의 영문 헤딩은 `DIELECTRIC CODE`이지만, 사용자에게 답변할 때는 항상 **온도특성 코드**라고 표기한다. `temperature characteristic`, `온도특성`, `dielectric code`는 모두 같은 필드를 가리킨다.

단일 문자 요청이 오면 온도특성 코드로 먼저 해석한다.

## Core Code Maps

### Size Code

- `R1 = 008004 / 0201`
- `02 = 01005 / 0402`
- `03 = 0201 / 0603`
- `05 = 0402 / 1005`
- `10 = 0603 / 1608`
- `21 = 0805 / 2012`
- `31 = 1206 / 3216`
- `32 = 1210 / 3225`
- `42 = 1808 / 4520`
- `43 = 1812 / 4532`
- `55 = 2220 / 5750`
- `L5 = 0204 / 0510`
- `L6 = 0304 / 0610`
- `01 = 0306 / 0816`
- `19 = 0503 / 1209`

### 온도특성 코드

Class I:

- `C = C0G`, operating `-55 to +125 C`, temp coefficient `0 +/- 30 ppm/C`
- `G = X8G`, operating `-55 to +150 C`, temp coefficient `0 +/- 30 ppm/C`

Class II:

- `A = X5R`, operating `-55 to +85 C`, capacitance change `+/-15%`
- `X = X6S`, operating `-55 to +105 C`, capacitance change `+/-22%`
- `W = X6T`, operating `-55 to +105 C`, capacitance change `-33 to +22%`
- `B = X7R`, operating `-55 to +125 C`, capacitance change `+/-15%`
- `K = X7R(S)`, operating `-55 to +125 C`, capacitance change `+/-15%`
- `Y = X7S`, operating `-55 to +125 C`, capacitance change `+/-22%`
- `Z = X7T`, operating `-55 to +125 C`, capacitance change `-33 to +22%`
- `F = Y5V`, operating `-30 to +85 C`, capacitance change `-82 to +22%`
- `M = X8M`, operating `-55 to +150 C`, capacitance change `-50 to +50%`
- `E = X8L`, operating `-55 to +150 C`, capacitance change `-40 to +15%`
- `J = JIS-B`, operating `-25 to +85 C`, capacitance change `+/-10%`

Note:

- `K = X7R(S)` is still X7R-family behavior, with the catalog note `DC Bias 0.5Vr TCC`.

### Capacitance Tolerance Code

- `N = +/-0.03 pF`
- `A = +/-0.05 pF`
- `B = +/-0.1 pF`
- `C = +/-0.25 pF`
- `H = +0.25 pF`
- `L = -0.25 pF`
- `D = +/-0.5 pF`
- `F = +/-1 pF` for values `< 10 pF`
- `F = +/-1%` for values `>= 10 pF`
- `G = +/-2%`
- `J = +/-5%`
- `U = +5%`
- `V = -5%`
- `K = +/-10%`
- `M = +/-20%`
- `Z = -20,+80%`

### Rated Voltage Code

- `S = 2.5Vdc`
- `R = 4.0Vdc`
- `Q = 6.3Vdc`
- `P = 10Vdc`
- `O = 16Vdc`
- `A = 25Vdc`
- `L = 35Vdc`
- `B = 50Vdc`
- `C = 100Vdc`
- `D = 200Vdc`
- `E = 250Vdc`
- `F = 350Vdc`
- `G = 500Vdc`
- `H = 630Vdc`
- `I = 1kVdc`
- `J = 2kVdc`
- `K = 3kVdc`

## Capacitance Code and Nominal Rules

### Capacitance Code Rule

- Express capacitance in `pF`
- Use `2 significant digits + number of zeros`
- For values `< 10 pF`, use `R` as the decimal point

Examples:

- `106 = 10 x 10^6 pF = 10,000,000 pF = 10 uF`
- `475 = 47 x 10^5 pF = 4,700,000 pF = 4.7 uF`
- `515 = 51 x 10^5 pF = 5,100,000 pF = 5.1 uF`
- `1R5 = 1.5 pF`

### Standard Nominal Series

Use the catalog's nominal series from `MLCC-003` when the requested nominal is not itself standard.

- `E-3 = 1.0, 2.2, 4.7`
- `E-6 = 1.0, 1.5, 2.2, 3.3, 4.7, 6.8`
- `E-12 = 1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2`
- `E-24 = 1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1`

Apply the series by decade. Example:

- `4.8 uF` is not a listed standard nominal, so report nearest standard options such as `4.7 uF (475)` and `5.1 uF (515)` instead of silently forcing one.

### Reliability and Family Routing

- `control code N = Standard`
- `control code W = Industrial / High Level I`
- `product or size control code 4 = Industrial / High Level II`

Use these application cues:

- `server`, `network`, `industrial power`, `humidity reliability` -> High Level I or II
- `outdoor`, `85C 85%RH 1000h` -> High Level II
- `bending`, `board flex`, `mechanical stress` -> High Bending Strength
- `audible noise`, `piezo`, `PAM`, `PMIC` -> Low Acoustic Noise
- `low inductance`, `high-speed IC`, `fewer chips` -> Low ESL
- `thin module`, `between solder balls`, `package` -> LSC
- `crack resistance`, `stacked structure`, `noise reduction` -> MFC
- no special cue -> Normal Standard

## Part-Number Skeleton Policy

Use the canonical skeleton:

`CL [size] [온도특성] [capacitance] [tolerance] [voltage] [thickness] [design] [product-or-size-control] [control] [packaging]`

Keep the 8th-11th codes unresolved unless directly supported by retrieved evidence.

Allowed forms:

- `CL03A475MR3?N?#`
- `CL03A515MR3[design TBD][product code TBD][control TBD][packaging TBD]`

Do not collapse unresolved fields into a fabricated full P/N.

## Active Lineup Pattern Policy

Use a separate DB-facing pattern when checking current products by `chip_prod_id`.

Rules:

- keep known literal code positions
- replace unknown single-character positions with `_`
- use `%` only when the DB lookup tool expects SQL-like variable-length matching

Examples:

- `CL32_106_O____`
- `%CL32_106_O____%`
- `CL03A515MR3____`

## Size and Thickness Filtering

When the user provides L/W/T max constraints, filter candidates in two stages before searching example parts.

### Stage 1: Size Code Filtering

Compare user L/W max against nominal size code dimensions. Reject any size code whose nominal L or W exceeds the user limit.

Examples:

- `L <= 0.690 mm, W <= 0.390 mm`
  - `03 (0201/0603 = 0.60 x 0.30)` -> pass
  - `05 (0402/1005 = 1.00 x 0.50)` -> reject: L and W exceed max
  - `02 (01005/0402 = 0.40 x 0.20)` -> pass, but capacitance feasibility is weak at this size
  - `10 (0603/1608 = 1.60 x 0.80)` -> reject: L exceeds max

### Stage 2: Thickness Code Filtering

After size codes pass, check the thickness code from `MLCC-003` against T max.

Examples:

- `0201/0603 -> thickness code 3 = 0.30 +/-0.03 mm` -> if T max = 0.550 mm, pass
- `01005/0402 -> thickness code 2 = 0.20 +/-0.02 mm` -> if T max = 0.550 mm, pass

### Stage 3: Family-Specific Dimensions

Specialty families have their own dimension tables that take priority over nominal size code dimensions. Check the family-specific reference chunk before concluding a size candidate passes.

- `LSC -> MLCC-009`
- `MFC -> MLCC-008`
- `High Bending Strength -> MLCC-010`
- `Low Acoustic Noise -> MLCC-011`
- `Low ESL -> MLCC-012`

Normal family candidates use nominal size + thickness code for first-pass filtering, then require datasheet verification for the exact physical envelope.

## Condition Relaxation Maps

When `active_lineup_lookup` returns 0 hits, use these ordered sequences to propose the nearest alternative code in each direction.

### Size Relaxation Order (small → large)

`R1` → `02` → `03` → `05` → `10` → `21` → `31` → `32` → `42` → `43` → `55`

Special sizes (`L5`, `L6`, `01`, `19`) do not participate in this linear order. If the current size is special, ask the user to specify the alternative explicitly.

### Voltage Relaxation Order (low → high)

`S (2.5V)` → `R (4V)` → `Q (6.3V)` → `P (10V)` → `O (16V)` → `A (25V)` → `L (35V)` → `B (50V)` → `C (100V)` → `D (200V)` → `E (250V)` → `F (350V)` → `G (500V)` → `H (630V)` → `I (1kV)` → `J (2kV)` → `K (3kV)`

### Capacitance Relaxation

Capacitance does not follow a single code sequence because the 3-digit code encodes the actual value. Instead, move to the nearest E-series nominal in the same decade:

- From `106 (10 uF)`: down → `685 (6.8 uF)`, up → `156 (15 uF)` or `226 (22 uF)`
- From `475 (4.7 uF)`: down → `335 (3.3 uF)`, up → `515 (5.1 uF)` or `685 (6.8 uF)`

Use the E-12 or E-24 series from the Standard Nominal Series section to find the next value up or down.

## Catalog Anomalies

- Some new-product rows appear inconsistent with the part-number rule and displayed capacitance. Treat them as anchors, then require datasheet confirmation.
- Some new-product rows appear duplicated. Do not treat duplication as stronger evidence.
