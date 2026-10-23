# The service, not the model, writes the report's source list

The model writes only the report body with `[n]` markers. The service appends `## Sources` from the run's stored `sources` rows and keeps only the cited ones. A `[n]` marker that refers to no stored source is counted in `citation_validity` and then removed. A stored report can therefore cite only URLs that were actually retrieved, at the cost that the model cannot cite a source it knows from training.

Source: SPEC.md D10 (§11), §7, §8
