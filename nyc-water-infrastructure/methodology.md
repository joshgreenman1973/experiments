# NYC water infrastructure -- methodology

## Data sources

### 1. Lead testing results

**Source:** NYC Department of Environmental Protection (DEP) Free Residential At-the-Tap Lead and Copper Testing Program

**API endpoint:** `https://data.cityofnewyork.us/resource/k5us-nav4.json`

**What it measures:** Lead and copper concentrations in drinking water collected at the tap inside residential buildings. Each record represents a test kit submitted by a resident, with two samples per kit: a "first draw" sample (water that has been sitting in pipes) and a sample taken after running the tap for 1-2 minutes ("flush" sample). Lead levels are reported in milligrams per liter (mg/L); these are converted to parts per billion (ppb) by multiplying by 1,000.

**EPA action level:** The Environmental Protection Agency's action level for lead in drinking water is 15 ppb (0.015 mg/L). This is not a safety threshold -- it is a regulatory trigger. When more than 10% of samples in a water system exceed 15 ppb, the utility must take corrective action. There is no known safe level of lead exposure.

**Important context:** NYC's water supply itself is essentially lead-free. Lead contamination occurs when water passes through lead service lines, lead solder, or lead-containing fixtures and fittings inside buildings. Older buildings (pre-1986) are more likely to have lead plumbing components.

### 2. Water main break reports

**Source:** NYC 311 complaints filed with the Department of Environmental Protection, filtered to the descriptor "Possible Water Main Break (Use Comments) (WA1)"

**API endpoint:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json` (filtered to DEP agency, water main break descriptor)

**What it captures:** 311 complaints reporting possible water main breaks. These are not confirmed breaks -- they are reports from the public of conditions that suggest a water main may have broken (e.g., water bubbling up from the street, flooding, loss of water pressure). Each record includes the date, location, borough, and resolution status.

**What counts as a "break":** A water main break occurs when one of the pressurized pipes in the city's underground water distribution network cracks, ruptures, or develops a significant leak. NYC has approximately 6,800 miles of water mains, some dating back to the mid-1800s. Breaks can be caused by age, corrosion, ground movement, temperature changes, or construction activity.

**How it is reported:** Residents call 311 or submit online complaints. DEP dispatches crews to investigate. Not every complaint corresponds to an actual break -- some may be hydrant leaks, service line issues, or other water problems. The resolution field in each record indicates the outcome of the investigation.

### 3. Drinking water quality

**Source:** NYC Department of Environmental Protection monthly water quality testing results at distribution points throughout the city

**API endpoint:** `https://data.cityofnewyork.us/resource/bkwf-xfky.json`

**What it measures:** Water quality parameters at sampling sites within the city's distribution system. These are not at-the-tap measurements -- they reflect water quality as it moves through the city's mains, before entering individual buildings. Key parameters include:

- **Turbidity (NTU):** A measure of water clarity. Higher turbidity means more suspended particles. The EPA maximum contaminant level for turbidity is 1 NTU for systems using conventional treatment, though NYC's filtered supply is typically well below this. Values below 0.5 NTU are considered excellent.

- **Residual free chlorine (mg/L):** Chlorine added during treatment to kill bacteria and other pathogens. The EPA requires a minimum detectable level (0.2 mg/L) throughout the distribution system. Typical NYC levels range from 0.2 to 1.5 mg/L. Higher levels may cause taste and odor issues but are not a health concern at distribution-system concentrations.

- **Total coliform (MPN/100mL):** Coliform bacteria are used as indicator organisms -- their presence suggests the water may have been contaminated. The EPA standard requires that no more than 5% of monthly samples test positive for total coliform. A result of "<1" means no coliform was detected.

- **E. coli (MPN/100mL):** A subset of coliform bacteria that specifically indicates fecal contamination. Any detection of E. coli in drinking water is a serious concern and triggers immediate action. A result of "<1" means none was detected.

- **Fluoride (mg/L):** Added to water to promote dental health. The recommended level is 0.7 mg/L. The EPA maximum contaminant level is 4.0 mg/L.

## Limitations

### Lead testing data

- **Self-selected sample:** The at-home testing program is voluntary. Residents who suspect lead problems may be more likely to request a test kit, which could bias results toward higher lead levels compared to the general housing stock.
- **Not representative of all buildings or units:** Only a fraction of NYC's roughly 1 million residential buildings have been tested. Coverage varies by neighborhood and building age.
- **Point-in-time measurement:** A single test captures conditions at one moment. Lead levels can vary based on time of day, water usage patterns, and how long water has been sitting in pipes.
- **No geographic coordinates:** The dataset includes ZIP code and borough but not precise addresses or coordinates, so the map displays results aggregated by ZIP code centroid rather than exact locations.

### Water main break data

- **Reports, not confirmed breaks:** These are 311 complaints, not engineering records of confirmed breaks. Some reports may be false alarms or duplicate complaints about the same incident.
- **Location may be approximate:** Complaint locations are based on what the caller reported and may not correspond precisely to where the break occurred.
- **Reporting bias:** Not all breaks are reported through 311. Some may be discovered by DEP crews or reported through other channels. Neighborhoods with higher 311 usage rates may appear to have more breaks.

### Water quality data

- **Distribution point measurements:** Water quality is measured at sampling sites in the distribution network, not at the tap inside buildings. Conditions can change between the sampling point and the faucet, especially in buildings with older internal plumbing.
- **No geographic detail:** The dataset identifies sampling sites by ID number but does not include geographic coordinates or neighborhood information.
- **Sampling frequency varies:** Not all parameters are measured at every sampling event. Fluoride data, for example, is not present in every record.
