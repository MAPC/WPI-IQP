# Analysis implementation notes

`src.analysis.run_analysis` consumes in-memory parsed assets and sites. Lists remain lists until export. The primary universe is accepted, explicitly field-validated, unique asset records. All-source exports retain quarantine rows, while vocabulary dictionaries use accepted records of every validation state.

The analysis produces all thirteen requested questions from computed tables. Asset descriptions use n, means, medians and quartiles. YES/NO/UNKNOWN are separate categories; known and all-validated denominators are explicit. Spearman rank correlations are descriptive and no significance tests are used. Asset observations share sites and cannot casually be treated as independent.

Site sensitivity is rebuilt from validated members only. Attributes, amenities and activities are unions; site access is any YES, all NO, else UNKNOWN. Transit and parking can come from different members. Broader accessibility richness removes the three focus tags to expose part-whole overlap.

`src.make_charts` creates eight paired PNG/SVG figures and a chart-source index. `src.workbook` produces four required Excel workbooks using the portable user-requested XlsxWriter stack. Counts/rates remain numeric, IDs stay text, and list cells use JSON. Saved files are reopened with openpyxl for schema/type/error checks. Visual workbook verification is recorded separately; native Excel automation is not assumed.

All findings, charts and workbooks are generated from the current inputs; no asset identities, current row totals or headline conclusions are embedded in implementation logic. Methodology source is `src.documentation`, so a clean rebuild also regenerates the dictionary and methodology outputs.
