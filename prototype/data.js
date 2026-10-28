/* Generated from pinned committed outputs. See tools/build-data.py. */
window.PILOT_DATA = {
  "source_commit": "739f411007a22f43a386983668e8a9ed8129b8c6",
  "sources": {
    "results/test/metrics.json": {
      "sha256": "3437c9168330a8be4c9552ba8f067ba191ec5123a46b63319e73f8c8a05fcee7",
      "bytes": 230299
    },
    "results/test/extras.json": {
      "sha256": "7395afa6396fe63281d72cdccb89cf72486d9b67388a41064bf7ca843bfafa97",
      "bytes": 580955
    },
    "results/storage.json": {
      "sha256": "189369663a6f0fb595d27c7f03c2c2a2e298ef368f16f07422bb2c86a6d1572a",
      "bytes": 113162
    }
  },
  "run_id": "20261028T012253Z",
  "covered": {
    "arrivals": [
      "2025-11-01T00:00:00Z",
      "2026-10-15T23:03:57Z"
    ],
    "drain": [
      "2026-10-15T23:03:57Z",
      "2026-10-25T00:00:00Z"
    ]
  },
  "cohort": {
    "n_jobs": {
      "value": 888224,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:cohort:n",
      "status": "ok",
      "reason": null
    },
    "declared_gpu_h": {
      "value": 11805978.330555556,
      "unit": "GPU_h",
      "evidence": "measured",
      "provenance_id": "20261028T012253Z:cohort:gpu_h",
      "status": "ok",
      "reason": null
    },
    "n_excluded": {
      "value": 8003,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:cohort:excluded",
      "status": "ok",
      "reason": null
    },
    "excluded_gpu_h": {
      "value": 382074.4236111111,
      "unit": "GPU_h",
      "evidence": "measured",
      "provenance_id": "20261028T012253Z:cohort:excluded_gpu_h",
      "status": "ok",
      "reason": null
    },
    "n_weeks": {
      "value": 51,
      "unit": "weeks",
      "evidence": "measured",
      "provenance_id": "20261028T012253Z:n_weeks",
      "status": "ok",
      "reason": null
    },
    "flex_shares": {
      "flexible": {
        "by_jobs": {
          "value": 0.4187130723781389,
          "unit": "fraction",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:share_flexible_jobs",
          "status": "ok",
          "reason": null
        },
        "by_gpu_h": {
          "value": 0.4568542182693726,
          "unit": "fraction",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:share_flexible_gpu_h",
          "status": "ok",
          "reason": null
        }
      },
      "mobile": {
        "by_jobs": {
          "value": 0.4187130723781389,
          "unit": "fraction",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:share_mobile_jobs",
          "status": "ok",
          "reason": null
        },
        "by_gpu_h": {
          "value": 0.4568542182693726,
          "unit": "fraction",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:share_mobile_gpu_h",
          "status": "ok",
          "reason": null
        }
      },
      "max_delay_s": {
        "0": {
          "value": 516313,
          "unit": "jobs",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:delay_0",
          "status": "ok",
          "reason": null
        },
        "3600": {
          "value": 283339,
          "unit": "jobs",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:delay_3600",
          "status": "ok",
          "reason": null
        },
        "21600": {
          "value": 88572,
          "unit": "jobs",
          "evidence": "assumed",
          "provenance_id": "20261028T012253Z:delay_21600",
          "status": "ok",
          "reason": null
        }
      }
    }
  },
  "workload": {
    "top_1pct_jobs_by_declared_gpu_h": {
      "definition": "the ceil(1%) of cohort jobs with the largest declared GPU-hours (ties to job_uid); their share of cohort execution energy (equal to their share of declared GPU-h, since every GPU-h carries 0.60 kW x PUE 1.20)",
      "n_jobs": {
        "value": 8883,
        "unit": "jobs",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:workload:top1pct:n",
        "status": "ok",
        "reason": null
      },
      "energy_kwh": {
        "value": 8034525.938999999,
        "unit": "kWh",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:workload:top1pct:kwh",
        "status": "ok",
        "reason": null
      },
      "energy_share": {
        "value": 0.9452044965460776,
        "unit": "fraction",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:workload:top1pct:share",
        "status": "ok",
        "reason": null
      }
    }
  },
  "baseline": {
    "n_jobs": {
      "value": 888224,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:n_jobs",
      "status": "ok",
      "reason": null
    },
    "requested_gpu_s": {
      "value": 42501521990.0,
      "unit": "GPU_s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:requested_gpu_s",
      "status": "ok",
      "reason": null
    },
    "completed_gpu_s": {
      "value": 42501521990.0,
      "unit": "GPU_s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:completed_gpu_s",
      "status": "ok",
      "reason": null
    },
    "late_jobs": {
      "value": 0,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:late_jobs",
      "status": "ok",
      "reason": null
    },
    "late_gpu_h": {
      "value": 0.0,
      "unit": "GPU_h",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:late_gpu_h",
      "status": "ok",
      "reason": null
    },
    "capacity_violations": {
      "value": 0,
      "unit": "sites",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:capacity_violations",
      "status": "ok",
      "reason": null
    },
    "wait_p50_s": {
      "value": 0.0,
      "unit": "s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:wait_p50_s",
      "status": "ok",
      "reason": null
    },
    "wait_p95_s": {
      "value": 0.0,
      "unit": "s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:wait_p95_s",
      "status": "ok",
      "reason": null
    },
    "wait_max_s": {
      "value": 6445.0,
      "unit": "s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:wait_max_s",
      "status": "ok",
      "reason": null
    },
    "wait_mean_s": {
      "value": 7.544627256187629,
      "unit": "s",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:wait_mean_s",
      "status": "ok",
      "reason": null
    },
    "execution_kwh": {
      "value": 8500304.398,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:execution_kwh",
      "status": "ok",
      "reason": null
    },
    "transfer_kwh": {
      "value": 0.0,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:transfer_kwh",
      "status": "ok",
      "reason": null
    },
    "transfer_it_kwh": {
      "value": 0.0,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:transfer_it_kwh",
      "status": "ok",
      "reason": null
    },
    "energy_kwh": {
      "value": 8500304.398,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:energy_kwh",
      "status": "ok",
      "reason": null
    },
    "kwh_share_tier_ge2": {
      "value": 0.00013748879396307002,
      "unit": "fraction",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:kwh_share_tier_ge2",
      "status": "ok",
      "reason": null
    },
    "execution_co2_kg": {
      "value": 4212139.562597102,
      "unit": "kg_CO2",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:execution_co2_kg",
      "status": "ok",
      "reason": null
    },
    "transfer_co2_kg": {
      "value": 0.0,
      "unit": "kg_CO2",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:transfer_co2_kg",
      "status": "ok",
      "reason": null
    },
    "co2_kg": {
      "value": 4212139.562597102,
      "unit": "kg_CO2",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:co2_kg",
      "status": "ok",
      "reason": null
    },
    "co2_kg_per_1000_gpu_h": {
      "value": 356.780221398127,
      "unit": "kg_CO2/1000_GPU_h",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:co2_kg_per_1000_gpu_h",
      "status": "ok",
      "reason": null
    },
    "moved_jobs": {
      "value": 0,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:moved_jobs",
      "status": "ok",
      "reason": null
    },
    "moved_share_jobs": {
      "value": 0.0,
      "unit": "fraction",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:moved_share_jobs",
      "status": "ok",
      "reason": null
    },
    "moved_share_energy": {
      "value": 0.0,
      "unit": "fraction",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:moved_share_energy",
      "status": "ok",
      "reason": null
    },
    "remote_jobs": {
      "value": 0,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:remote_jobs",
      "status": "ok",
      "reason": null
    },
    "remote_energy_share": {
      "value": 0.0,
      "unit": "fraction",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:remote_energy_share",
      "status": "ok",
      "reason": null
    },
    "blocked_jobs": {
      "value": null,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:blocked_jobs",
      "status": "not_run",
      "reason": "F14.7 is reported for G, S, K, W, L and H only"
    },
    "blocked_kwh": {
      "value": null,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:blocked_kwh",
      "status": "not_run",
      "reason": "F14.7 is reported for G, S, K, W, L and H only"
    },
    "fit_rejected_jobs": {
      "value": 0,
      "unit": "jobs",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:fit_rejected_jobs",
      "status": "ok",
      "reason": null
    },
    "fit_rejected_kwh": {
      "value": 0.0,
      "unit": "kWh",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:fit_rejected_kwh",
      "status": "ok",
      "reason": null
    },
    "mobile_remote_share": {
      "value": 0.0,
      "unit": "fraction",
      "evidence": "simulated",
      "provenance_id": "20261028T012253Z:U:mobile_remote",
      "status": "ok",
      "reason": null
    },
    "peak_gpus": {
      "PACE": {
        "value": 2288,
        "unit": "GPUs",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:peak_gpus:PACE",
        "status": "ok",
        "reason": null
      },
      "CISO": {
        "value": 0,
        "unit": "GPUs",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:peak_gpus:CISO",
        "status": "ok",
        "reason": null
      },
      "BPAT": {
        "value": 0,
        "unit": "GPUs",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:peak_gpus:BPAT",
        "status": "ok",
        "reason": null
      },
      "NEVP": {
        "value": 0,
        "unit": "GPUs",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:peak_gpus:NEVP",
        "status": "ok",
        "reason": null
      }
    },
    "execution_kwh_by_site": {
      "PACE": {
        "value": 8500304.398,
        "unit": "kWh",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:execution_kwh:PACE",
        "status": "ok",
        "reason": null
      },
      "CISO": {
        "value": 0.0,
        "unit": "kWh",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:execution_kwh:CISO",
        "status": "ok",
        "reason": null
      },
      "BPAT": {
        "value": 0.0,
        "unit": "kWh",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:execution_kwh:BPAT",
        "status": "ok",
        "reason": null
      },
      "NEVP": {
        "value": 0.0,
        "unit": "kWh",
        "evidence": "simulated",
        "provenance_id": "20261028T012253Z:U:execution_kwh:NEVP",
        "status": "ok",
        "reason": null
      }
    }
  },
  "routing": {
    "primary": {
      "contrast": {
        "primary": true,
        "labels": [],
        "n_weeks": {
          "value": 51,
          "unit": "weeks",
          "evidence": "measured",
          "provenance_id": "20261028T012253Z:S_vs_U:b4:n_weeks",
          "status": "ok",
          "reason": null
        },
        "reps": {
          "value": 2000,
          "unit": "replicates",
          "evidence": "assumed",
          "provenance_id": "F12.4:reps",
          "status": "ok",
          "reason": null
        },
        "diff_kg": {
          "value": 937773.9761488046,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S_vs_U:b4:diff_kg",
          "status": "ok",
          "reason": null
        },
        "diff_kg_ci95": {
          "value": [
            755608.481269292,
            1103473.5198786398
          ],
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S_vs_U:b4:diff_kg_ci",
          "status": "ok",
          "reason": null
        },
        "saving": {
          "value": 0.22263601720988474,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S_vs_U:b4:saving",
          "status": "ok",
          "reason": null
        },
        "saving_ci95": {
          "value": [
            0.17340216944938253,
            0.2719699360498792
          ],
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S_vs_U:b4:saving_ci",
          "status": "ok",
          "reason": null
        }
      },
      "metrics": {
        "n_jobs": {
          "value": 888224,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:n_jobs",
          "status": "ok",
          "reason": null
        },
        "requested_gpu_s": {
          "value": 42501521990.0,
          "unit": "GPU_s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:requested_gpu_s",
          "status": "ok",
          "reason": null
        },
        "completed_gpu_s": {
          "value": 42501521990.0,
          "unit": "GPU_s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:completed_gpu_s",
          "status": "ok",
          "reason": null
        },
        "late_jobs": {
          "value": 0,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:late_jobs",
          "status": "ok",
          "reason": null
        },
        "late_gpu_h": {
          "value": 0.0,
          "unit": "GPU_h",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:late_gpu_h",
          "status": "ok",
          "reason": null
        },
        "capacity_violations": {
          "value": 0,
          "unit": "sites",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:capacity_violations",
          "status": "ok",
          "reason": null
        },
        "wait_p50_s": {
          "value": 0.0,
          "unit": "s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:wait_p50_s",
          "status": "ok",
          "reason": null
        },
        "wait_p95_s": {
          "value": 3192.0,
          "unit": "s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:wait_p95_s",
          "status": "ok",
          "reason": null
        },
        "wait_max_s": {
          "value": 21600.0,
          "unit": "s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:wait_max_s",
          "status": "ok",
          "reason": null
        },
        "wait_mean_s": {
          "value": 1126.1366772345714,
          "unit": "s",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:wait_mean_s",
          "status": "ok",
          "reason": null
        },
        "execution_kwh": {
          "value": 8500304.398,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:execution_kwh",
          "status": "ok",
          "reason": null
        },
        "transfer_kwh": {
          "value": 123130.27932,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:transfer_kwh",
          "status": "ok",
          "reason": null
        },
        "transfer_it_kwh": {
          "value": 102608.5661,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:transfer_it_kwh",
          "status": "ok",
          "reason": null
        },
        "energy_kwh": {
          "value": 8623434.67732,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:energy_kwh",
          "status": "ok",
          "reason": null
        },
        "kwh_share_tier_ge2": {
          "value": 0.0012240907521178747,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:kwh_share_tier_ge2",
          "status": "ok",
          "reason": null
        },
        "execution_co2_kg": {
          "value": 3236385.2061985363,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:execution_co2_kg",
          "status": "ok",
          "reason": null
        },
        "transfer_co2_kg": {
          "value": 37980.38024976121,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:transfer_co2_kg",
          "status": "ok",
          "reason": null
        },
        "co2_kg": {
          "value": 3274365.5864482974,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:co2_kg",
          "status": "ok",
          "reason": null
        },
        "co2_kg_per_1000_gpu_h": {
          "value": 277.3480938867872,
          "unit": "kg_CO2/1000_GPU_h",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:co2_kg_per_1000_gpu_h",
          "status": "ok",
          "reason": null
        },
        "moved_jobs": {
          "value": 373633,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:moved_jobs",
          "status": "ok",
          "reason": null
        },
        "moved_share_jobs": {
          "value": 0.42065177252584934,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:moved_share_jobs",
          "status": "ok",
          "reason": null
        },
        "moved_share_energy": {
          "value": 0.2907052861049788,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:moved_share_energy",
          "status": "ok",
          "reason": null
        },
        "remote_jobs": {
          "value": 371390,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:remote_jobs",
          "status": "ok",
          "reason": null
        },
        "remote_energy_share": {
          "value": 0.2998498814539171,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:remote_energy_share",
          "status": "ok",
          "reason": null
        },
        "blocked_jobs": {
          "value": 62,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:blocked_jobs",
          "status": "ok",
          "reason": null
        },
        "blocked_kwh": {
          "value": 18.0728,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:blocked_kwh",
          "status": "ok",
          "reason": null
        },
        "fit_rejected_jobs": {
          "value": 0,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:fit_rejected_jobs",
          "status": "ok",
          "reason": null
        },
        "fit_rejected_kwh": {
          "value": 0.0,
          "unit": "kWh",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:fit_rejected_kwh",
          "status": "ok",
          "reason": null
        },
        "mobile_remote_share": {
          "value": 0.9985991272105423,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:S:mobile_remote",
          "status": "ok",
          "reason": null
        },
        "peak_gpus": {
          "PACE": {
            "value": 2288,
            "unit": "GPUs",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:peak_gpus:PACE",
            "status": "ok",
            "reason": null
          },
          "CISO": {
            "value": 512,
            "unit": "GPUs",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:peak_gpus:CISO",
            "status": "ok",
            "reason": null
          },
          "BPAT": {
            "value": 512,
            "unit": "GPUs",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:peak_gpus:BPAT",
            "status": "ok",
            "reason": null
          },
          "NEVP": {
            "value": 512,
            "unit": "GPUs",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:peak_gpus:NEVP",
            "status": "ok",
            "reason": null
          }
        },
        "execution_kwh_by_site": {
          "PACE": {
            "value": 6037698.8116,
            "unit": "kWh",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:execution_kwh:PACE",
            "status": "ok",
            "reason": null
          },
          "CISO": {
            "value": 623964.8308,
            "unit": "kWh",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:execution_kwh:CISO",
            "status": "ok",
            "reason": null
          },
          "BPAT": {
            "value": 1735161.6884,
            "unit": "kWh",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:execution_kwh:BPAT",
            "status": "ok",
            "reason": null
          },
          "NEVP": {
            "value": 103479.0672,
            "unit": "kWh",
            "evidence": "simulated",
            "provenance_id": "20261028T012253Z:S:execution_kwh:NEVP",
            "status": "ok",
            "reason": null
          }
        }
      },
      "run_id": "20261028T012253Z",
      "source": "results/test/metrics.json",
      "field": "contrasts[candidate=S, reference=U].blocks.4"
    },
    "limited": {
      "contrast": {
        "primary": true,
        "labels": [],
        "n_weeks": {
          "value": 51,
          "unit": "weeks",
          "evidence": "measured",
          "provenance_id": "20261028T022912Z:S_vs_U:b4:n_weeks",
          "status": "ok",
          "reason": null
        },
        "reps": {
          "value": 2000,
          "unit": "replicates",
          "evidence": "assumed",
          "provenance_id": "F12.4:reps",
          "status": "ok",
          "reason": null
        },
        "diff_kg": {
          "value": 132809.4937733193,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S_vs_U:b4:diff_kg",
          "status": "ok",
          "reason": null
        },
        "diff_kg_ci95": {
          "value": [
            82714.16866679136,
            186529.05780466177
          ],
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S_vs_U:b4:diff_kg_ci",
          "status": "ok",
          "reason": null
        },
        "saving": {
          "value": 0.031530174107391694,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S_vs_U:b4:saving",
          "status": "ok",
          "reason": null
        },
        "saving_ci95": {
          "value": [
            0.018916042693620575,
            0.04672596098659322
          ],
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S_vs_U:b4:saving_ci",
          "status": "ok",
          "reason": null
        }
      },
      "metrics": {
        "co2_kg": {
          "value": 4079330.0688237823,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S:co2_kg",
          "status": "ok",
          "reason": null
        },
        "late_jobs": {
          "value": 0,
          "unit": "jobs",
          "evidence": "simulated",
          "provenance_id": "20261028T022912Z:S:late_jobs",
          "status": "ok",
          "reason": null
        },
        "feasible": true
      },
      "run_id": "20261028T022912Z",
      "source": "results/test/extras.json",
      "field": "extensions.mobility_le_8gpus.vs_U.S.4"
    },
    "timing": {
      "contrast": {
        "primary": true,
        "labels": [],
        "n_weeks": {
          "value": 51,
          "unit": "weeks",
          "evidence": "measured",
          "provenance_id": "20261028T012253Z:W_time_vs_U:b4:n_weeks",
          "status": "ok",
          "reason": null
        },
        "reps": {
          "value": 2000,
          "unit": "replicates",
          "evidence": "assumed",
          "provenance_id": "F12.4:reps",
          "status": "ok",
          "reason": null
        },
        "diff_kg": {
          "value": 32613.718121973798,
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:W_time_vs_U:b4:diff_kg",
          "status": "ok",
          "reason": null
        },
        "diff_kg_ci95": {
          "value": [
            25552.27185966908,
            40025.16833765102
          ],
          "unit": "kg_CO2",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:W_time_vs_U:b4:diff_kg_ci",
          "status": "ok",
          "reason": null
        },
        "saving": {
          "value": 0.00774279143349775,
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:W_time_vs_U:b4:saving",
          "status": "ok",
          "reason": null
        },
        "saving_ci95": {
          "value": [
            0.00582093758970219,
            0.009961329397111
          ],
          "unit": "fraction",
          "evidence": "simulated",
          "provenance_id": "20261028T012253Z:W_time_vs_U:b4:saving_ci",
          "status": "ok",
          "reason": null
        }
      }
    }
  },
  "knobs": {
    "dest_slots": {
      "value": 512,
      "unit": "GPU_slots",
      "evidence": "assumed",
      "provenance_id": "20261028T022912Z:scenario:dest_slots",
      "status": "ok",
      "reason": null
    },
    "transfer_s": {
      "value": 1800.0,
      "unit": "s",
      "evidence": "assumed",
      "provenance_id": "20261028T022912Z:scenario:transfer_s",
      "status": "ok",
      "reason": null
    },
    "batch_delay_s": {
      "value": 21600,
      "unit": "s",
      "evidence": "assumed",
      "provenance_id": "20261028T022912Z:scenario:batch_delay_s",
      "status": "ok",
      "reason": null
    },
    "mobility_max_gpus": {
      "value": 8,
      "unit": "GPUs",
      "evidence": "assumed",
      "provenance_id": "20261028T022912Z:scenario:mobility_max_gpus",
      "status": "ok",
      "reason": null
    },
    "phase_days": {
      "value": 0,
      "unit": "days",
      "evidence": "assumed",
      "provenance_id": "20261028T022912Z:scenario:phase_days",
      "status": "ok",
      "reason": null
    }
  },
  "storage": {
    "run_id": "20261028T023856Z",
    "window": {
      "start": "2025-11-01T00:00:00Z",
      "end": "2026-10-24T00:00:00Z",
      "n_hours": {
        "value": 8568,
        "unit": "hours",
        "evidence": "measured",
        "provenance_id": "extras:storage:n_hours",
        "status": "ok",
        "reason": null
      }
    },
    "rush": {
      "threshold_mw": {
        "value": 7207.329999999998,
        "unit": "MW",
        "evidence": "observed",
        "provenance_id": "extras:storage:rush:thr",
        "status": "ok",
        "reason": null
      },
      "threshold_source": "results/storage.json (the training years' 99% quantile)",
      "n_hours": {
        "value": 14,
        "unit": "hours",
        "evidence": "measured",
        "provenance_id": "extras:storage:rush:n",
        "status": "ok",
        "reason": null
      },
      "peak_net_load_mw": {
        "value": 7717.0,
        "unit": "MW",
        "evidence": "observed",
        "provenance_id": "extras:storage:rush:peak",
        "status": "ok",
        "reason": null
      },
      "peak_hour_utc": "2026-08-21T01:00:00Z"
    },
    "assumptions": {
      "sizes_mwh": {
        "value": [
          0,
          1,
          2,
          4,
          8,
          12,
          16,
          24
        ],
        "unit": "MWh",
        "evidence": "assumed",
        "provenance_id": "storage:sizes",
        "status": "ok",
        "reason": null
      },
      "p_over_e": {
        "value": 0.25,
        "unit": "1/h",
        "evidence": "assumed",
        "provenance_id": "storage:p_over_e",
        "status": "ok",
        "reason": null
      },
      "etas": {
        "value": [
          0.75,
          0.85,
          0.9
        ],
        "unit": "fraction",
        "evidence": "assumed",
        "provenance_id": "storage:etas",
        "status": "ok",
        "reason": null
      },
      "eta_default": {
        "value": 0.85,
        "unit": "fraction",
        "evidence": "assumed",
        "provenance_id": "storage:eta_default",
        "status": "ok",
        "reason": null
      },
      "connection_mw": {
        "value": 1.64736,
        "unit": "MW",
        "evidence": "assumed",
        "provenance_id": "storage:connection",
        "status": "ok",
        "reason": null
      },
      "kw_per_gpu": {
        "value": 0.6,
        "unit": "kW",
        "evidence": "assumed",
        "provenance_id": "storage:kw_per_gpu",
        "status": "ok",
        "reason": null
      },
      "pue": {
        "value": 1.2,
        "unit": "ratio",
        "evidence": "assumed",
        "provenance_id": "storage:pue",
        "status": "ok",
        "reason": null
      },
      "losses": "round-trip losses charged on the charging side (stores η × grid draw)",
      "power_limit": "charging ≤ min(P, connection − cluster load); discharge ≤ min(P, cluster load); connection = 2,288 GPUs × 0.60 kW × PUE 1.20",
      "state_of_charge": "chronological over the whole window, starting empty; energy left at the end is valued at zero",
      "ignored": "degradation, self-discharge, auxiliary loads, capital cost",
      "load": "cohort jobs only (warm-up occupancy not included), exact hourly overlap"
    },
    "headline": {
      "rule": "illustrative selection (lead ruling, T10b fix round 1): 4 MWh / 1 MW, sized to the charging room the site connection leaves free; not an optimum",
      "e_mwh": {
        "value": 4.0,
        "unit": "MWh",
        "evidence": "simulated",
        "provenance_id": "storage:headline:e",
        "status": "ok",
        "reason": null
      },
      "plateau_rule": "the smallest size whose fixed-schedule (A) cut, U load, η 0.85, is at least 90% of A's largest cut over the size grid",
      "plateau_e_mwh": {
        "value": 8,
        "unit": "MWh",
        "evidence": "simulated",
        "provenance_id": "storage:headline:plateau",
        "status": "ok",
        "reason": null
      }
    },
    "schedules": {
      "carbon": {
        "charge_hours": {
          "value": [
            10,
            11,
            12,
            13,
            14,
            15
          ],
          "unit": "local_hour",
          "evidence": "assumed",
          "provenance_id": "extras:storage:2b:carbon:charge",
          "status": "ok",
          "reason": null
        },
        "discharge_hours": {
          "value": [
            0,
            1,
            6,
            21,
            22,
            23
          ],
          "unit": "local_hour",
          "evidence": "assumed",
          "provenance_id": "extras:storage:2b:carbon:discharge",
          "status": "ok",
          "reason": null
        },
        "metrics": {
          "co2_t": {
            "value": 4045.6682325478578,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:co2",
            "status": "ok",
            "reason": null
          },
          "base_co2_t": {
            "value": 4212.1395625971145,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:base",
            "status": "ok",
            "reason": null
          },
          "cut_t": {
            "value": 166.4713300492568,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:cut",
            "status": "ok",
            "reason": null
          },
          "cut_frac": {
            "value": 0.039521798263164425,
            "unit": "fraction",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:cut_frac",
            "status": "ok",
            "reason": null
          },
          "flat_marginal_cut_t": {
            "value": -107.07711403371532,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:flat",
            "status": "ok",
            "reason": null
          },
          "rush_import_before_mw": {
            "value": 0.8789749285714286,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:rush0",
            "status": "ok",
            "reason": null
          },
          "rush_import_after_mw": {
            "value": 0.5524917285714286,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:rush1",
            "status": "ok",
            "reason": null
          },
          "peak_import_before_mw": {
            "value": 1.6391664,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:peak0",
            "status": "ok",
            "reason": null
          },
          "peak_import_after_mw": {
            "value": 1.64736,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:peak1",
            "status": "ok",
            "reason": null
          },
          "rush_hours_discharging": {
            "value": 6,
            "unit": "hours",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:carbon:U:4:rush_dis",
            "status": "ok",
            "reason": null
          }
        }
      },
      "peak": {
        "charge_hours": {
          "value": [
            8,
            9,
            10,
            14
          ],
          "unit": "local_hour",
          "evidence": "assumed",
          "provenance_id": "extras:storage:2b:peak:charge",
          "status": "ok",
          "reason": null
        },
        "discharge_hours": {
          "value": [
            18,
            19,
            20,
            21
          ],
          "unit": "local_hour",
          "evidence": "assumed",
          "provenance_id": "extras:storage:2b:peak:discharge",
          "status": "ok",
          "reason": null
        },
        "metrics": {
          "co2_t": {
            "value": 4171.276128312704,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:co2",
            "status": "ok",
            "reason": null
          },
          "base_co2_t": {
            "value": 4212.1395625971145,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:base",
            "status": "ok",
            "reason": null
          },
          "cut_t": {
            "value": 40.86343428441044,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:cut",
            "status": "ok",
            "reason": null
          },
          "cut_frac": {
            "value": 0.009701348608500266,
            "unit": "fraction",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:cut_frac",
            "status": "ok",
            "reason": null
          },
          "flat_marginal_cut_t": {
            "value": -77.01073417446005,
            "unit": "t_CO2",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:flat",
            "status": "ok",
            "reason": null
          },
          "rush_import_before_mw": {
            "value": 0.8789749285714286,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:rush0",
            "status": "ok",
            "reason": null
          },
          "rush_import_after_mw": {
            "value": 0.31665316,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:rush1",
            "status": "ok",
            "reason": null
          },
          "peak_import_before_mw": {
            "value": 1.6391664,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:peak0",
            "status": "ok",
            "reason": null
          },
          "peak_import_after_mw": {
            "value": 1.64736,
            "unit": "MW",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:peak1",
            "status": "ok",
            "reason": null
          },
          "rush_hours_discharging": {
            "value": 10,
            "unit": "hours",
            "evidence": "simulated",
            "provenance_id": "extras:storage:2b:peak:U:4:rush_dis",
            "status": "ok",
            "reason": null
          }
        }
      }
    }
  }
};
