# Independent public test data

maternal_risk_uci.csv is the original UCI Maternal Health Risk CSV downloaded
directly for the new BloomCare project. It lets regression tests train an
isolated real model without a network connection or the user's active model.
Tests create their model and database in temporary directories; they do not
replace the application artifact or use live patient records.

Ahmed, M. (2020). Maternal Health Risk [Dataset]. UCI Machine Learning
Repository. https://doi.org/10.24432/C5DP5D.
Source: https://archive.ics.uci.edu/dataset/863/maternal+health+risk.
License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/.
SHA-256: a1f7025719f84715096e0d1f95ae2e56b57809b9b15449e1836c96a7d976ae9b.

The source file is unmodified. Preprocessing and a grouped split are applied
only inside training. No old BloomCare source, weights, or data copies are used.
