# RAG chunking benchmark

Docs: Pharmaceutical_Product_Selection_Application_of_AH.pdf, Drug Development From Concept to Marketing.pdf, Tormay2015_Article_BigDataInPharmaceuticalRDCreat.pdf, BIGDATA_Pharmaceutical_Industry.pdf

| strategy | avg chunks/doc | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | query ms p50 |
|---|---|---|---|---|---|---|
| fixed | 30.5 | 0.8 | 0.933 | 0.86 | 0.886 | 65.065 |
| recursive | 29.5 | 0.8 | 1.0 | 0.89 | 0.918 | 61.962 |
| parent | 91.0 | 0.933 | 0.967 | 0.95 | 0.958 | 61.865 |
