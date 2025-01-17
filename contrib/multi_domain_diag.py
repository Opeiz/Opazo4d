from pathlib import Path
import xarray as xr
import pandas as pd
import torch
import einops
import numpy as np
import scipy.ndimage as ndi
import omegaconf
from omegaconf import OmegaConf
import src.utils
import hydra


def load_cfg_from_xp(xpd, key, overrides=None, call=True):
    xpd = Path(xpd)
    src_cfg, xp = src.utils.load_cfg(xpd / ".hydra")
    overrides = overrides or dict()
    OmegaConf.set_struct(src_cfg, True)
    with omegaconf.open_dict(src_cfg):
        cfg = OmegaConf.merge(src_cfg, overrides)
    node = OmegaConf.select(cfg, key)
    return hydra.utils.call(node) if call else node


def get_smooth_spat_rec_weight(orig_rec_weight):
    # orig_rec_weight = src.utils.get_triang_time_wei(cfg.datamodule.xrds_kw.patch_dims, crop=dict(lat=20, lon=20))
    rec_weight = ndi.gaussian_filter(orig_rec_weight, sigma=[0, 25, 25])
    rec_weight = np.where(
        rec_weight > einops.reduce(rec_weight, "t lat lon -> t () ()", np.median),
        rec_weight,
        0,
    )
    min_non_null = einops.reduce(
        np.where(rec_weight > 0, rec_weight, 1000), "t lat lon -> t () ()", "min"
    )
    rec_weight = rec_weight - min_non_null * (rec_weight > 0)
    rec_weight = np.where(
        orig_rec_weight > 0, ndi.gaussian_filter(rec_weight, sigma=[0, 10, 10]), 0
    )
    return rec_weight


def multi_domain_osse_diag(
    trainer,
    lit_mod,
    dm,
    ckpt_path,
    test_domains,
    test_periods,
    rec_weight=None,
    save_dir=None,
    src_dm=None,
):
    ckpt = torch.load(ckpt_path)["state_dict"]
    lit_mod.load_state_dict(ckpt)

    if rec_weight is not None:
        lit_mod.rec_weight = torch.from_numpy(rec_weight)

    norm_dm = src_dm or dm
    lit_mod.norm_stats = norm_dm.norm_stats()

    trainer.test(lit_mod, datamodule=dm)

    tdat = lit_mod.test_data
    tdat = tdat.assign(rec_ssh=tdat.rec_ssh.where(np.isfinite(tdat.ssh), np.nan)).drop("obs")

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

    tdat.to_netcdf(save_dir / "multi_domain_tdat.nc")
    
    metrics_df = multi_domain_osse_metrics(tdat, test_domains, test_periods)

    print("==== Metrics ====")
    print(metrics_df.to_markdown())
    metrics_df.to_csv(save_dir / "multi_domain_metrics.csv")


def multi_domain_osse_metrics(tdat, test_domains, test_periods):
    metrics = []
    for d in test_domains:
        for p in test_periods:
            tdom_spat = test_domains[d].test
            test_domain = dict(time=slice(*p), **tdom_spat)

            da_rec, da_ref = tdat.sel(test_domain).drop("ssh") ,tdat.sel(test_domain).ssh

            leaderboard_rmse = (
                1.0 - (((da_rec - da_ref) ** 2).mean()) ** 0.5 / (((da_ref) ** 2).mean()) ** 0.5
            )
            
            psd, lx, lt = src.utils.psd_based_scores(
                da_rec.rec_ssh.pipe(lambda da: xr.apply_ufunc(np.nan_to_num, da,)),
                da_ref.copy().pipe(lambda da: xr.apply_ufunc(np.nan_to_num, da,)),
            )
            mdf = (
                pd.DataFrame(
                    [
                        {
                            "domain": d,
                            "period": p,
                            "variable": "rec_ssh",
                            "lt": lt,
                            "lx": lx,
                            "LON": "[" + str((test_domains[d].test["lon"]).start) + " | " + str((test_domains[d].test["lon"]).stop) + "]",
                            "LAT": "[" + str((test_domains[d].test["lat"]).start) + " | " + str((test_domains[d].test["lat"]).stop) + "]",
                        },
                    ]
                )
                .set_index("variable")
                .join(round(leaderboard_rmse.to_array().to_dataframe(name="mu"),5))
            )
            metrics.append(mdf)
    
    metrics_df = pd.concat(metrics).sort_values(by='mu')
    print("==== Metrics ====")
    print(metrics_df.to_markdown())
    # metrics_df.to_csv("multi_domain_metrics.csv")

    return metrics_df


def load_oi_4nadirs():
    oi = xr.open_dataset('../sla-data-registry/NATL60/NATL/oi/ssh_NATL60_4nadir.nc')
    ssh = xr.open_dataset('../sla-data-registry/NATL60/NATL/ref_new/NATL60-CJM165_NATL_ssh_y2013.1y.nc')
    ssh['time'] = pd.to_datetime('2012-10-01') + pd.to_timedelta(ssh.time, 's') 
    
    exit = ssh.assign(rec_ssh=oi.ssh_mod.interp(time=ssh.time, lat=ssh.lat, lon=ssh.lon, method='nearest').where(lambda ds: np.abs(ds) < 10, np.nan))
    return exit

def load_oi_swot():
    oi = xr.open_dataset('../sla-data-registry/NATL60/NATL/oi/ssh_NATL60_swot.nc')
    ssh = xr.open_dataset('../sla-data-registry/NATL60/NATL/ref_new/NATL60-CJM165_NATL_ssh_y2013.1y.nc')
    ssh['time'] = pd.to_datetime('2012-10-01') + pd.to_timedelta(ssh.time, 's') 
    
    exit = ssh.assign(rec_ssh=oi.ssh_mod.interp(time=ssh.time, lat=ssh.lat, lon=ssh.lon, method='nearest').where(lambda ds: np.abs(ds) < 10, np.nan))
    return exit

def load_oi_swot_4nadirs():
    oi = xr.open_dataset('../sla-data-registry/NATL60/NATL/oi/ssh_NATL60_swot_4nadir.nc')
    ssh = xr.open_dataset('../sla-data-registry/NATL60/NATL/ref_new/NATL60-CJM165_NATL_ssh_y2013.1y.nc')
    ssh['time'] = pd.to_datetime('2012-10-01') + pd.to_timedelta(ssh.time, 's') 
    
    exit = ssh.assign(rec_ssh=oi.ssh_mod.interp(time=ssh.time, lat=ssh.lat, lon=ssh.lon, method='nearest').where(lambda ds: np.abs(ds) < 10, np.nan))
    return exit

def load_miost():
    miost = xr.open_dataset('../sla-data-registry/enatl_preproc/miost_nadirs.nc')
    ssh =  xr.open_zarr('../sla-data-registry/enatl_preproc/truth_SLA_SSH_NATL60.zarr').load()
    miost = miost.rename({"latitude":'lat',"longitude":'lon'})
    
    tdat = ssh.assign(rec_ssh=miost.ssh.interp(time=ssh.time, lat=ssh.lat, lon=ssh.lon, method='nearest').where(lambda ds: np.abs(ds) < 10, np.nan))
    return tdat