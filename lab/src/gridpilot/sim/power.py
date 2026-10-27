"""The power model's constants: one source for carbon_search, accounting and run_slice
(Stage 3 T9, A14). They are `assumed` (spec F7) and exported in the manifest's assumptions."""

GPU_KW = 0.60  # active power per allocated GPU slot (assumed, F7)
PUE = 1.20  # at every site (assumed, F7)
TRANSFER_FRACTION = 0.05  # transfer IT energy as a share of the job's IT energy (assumed, F7)
