"""Patch script: fix BSDF absorption in MP path of _trace_single_source."""

content = open('backlight_sim/sim/tracer.py', 'r', encoding='utf-8').read()

old = (
    "                # BSDF dispatch\n"
    "                bsdf_name_mp = getattr(mat, 'bsdf_profile_name', '')\n"
    "                if bsdf_name_mp and bsdf_cdf_cache_mp.get(bsdf_name_mp) is not None:\n"
    "                    bsdf_prof_mp = (getattr(project, 'bsdf_profiles', {}) or {}).get(bsdf_name_mp, {})\n"
    "                    cdfs_mp = bsdf_cdf_cache_mp[bsdf_name_mp]\n"
    "                    theta_in_vals_mp = cdfs_mp['theta_in']\n"
    "                    refl_total_mp = cdfs_mp['refl_total']\n"
    "                    trans_total_mp = cdfs_mp['trans_total']\n"
    "                    cos_i_mp = np.clip(np.einsum('ij,j->i', -directions[hit_idx], on[0]), 0.0, 1.0)\n"
    "                    theta_i_deg_mp = np.degrees(np.arccos(cos_i_mp))\n"
    "                    bin_idx_mp = np.clip(\n"
    "                        np.searchsorted(theta_in_vals_mp, theta_i_deg_mp, side='right') - 1,\n"
    "                        0, len(theta_in_vals_mp) - 1\n"
    "                    )\n"
    "                    r_total_mp = refl_total_mp[bin_idx_mp]\n"
    "                    t_total_mp = trans_total_mp[bin_idx_mp]\n"
    "                    rt_sum_mp = r_total_mp + t_total_mp\n"
    "                    absorption_frac_mp = np.where(rt_sum_mp > 0, 1.0 - np.minimum(rt_sum_mp, 1.0), 1.0)\n"
    "                    weights[hit_idx] *= (1.0 - absorption_frac_mp)\n"
    "                    roll_mp = rng.random(len(hit_idx))\n"
    "                    p_refl_mp = np.where(rt_sum_mp > 0, r_total_mp / np.maximum(rt_sum_mp, 1e-12), 1.0)\n"
    "                    refl_bsdf_mp = roll_mp < p_refl_mp\n"
    "                    trans_bsdf_mp = ~refl_bsdf_mp\n"
)

new = (
    "                # BSDF dispatch\n"
    "                bsdf_name_mp = getattr(mat, 'bsdf_profile_name', '')\n"
    "                if bsdf_name_mp and bsdf_cdf_cache_mp.get(bsdf_name_mp) is not None:\n"
    "                    bsdf_prof_mp = (getattr(project, 'bsdf_profiles', {}) or {}).get(bsdf_name_mp, {})\n"
    "                    cdfs_mp = bsdf_cdf_cache_mp[bsdf_name_mp]\n"
    "                    # Apply reflectance weight scaling (energy conservation)\n"
    "                    weights[hit_idx] *= mat.reflectance\n"
    "                    # Determine R/T probability from BSDF angular distribution\n"
    "                    theta_in_vals_mp = cdfs_mp['theta_in']\n"
    "                    refl_total_mp = cdfs_mp['refl_total']\n"
    "                    trans_total_mp = cdfs_mp['trans_total']\n"
    "                    cos_i_mp = np.clip(np.einsum('ij,j->i', -directions[hit_idx], on[0]), 0.0, 1.0)\n"
    "                    theta_i_deg_mp = np.degrees(np.arccos(cos_i_mp))\n"
    "                    bin_idx_mp = np.clip(\n"
    "                        np.searchsorted(theta_in_vals_mp, theta_i_deg_mp, side='right') - 1,\n"
    "                        0, len(theta_in_vals_mp) - 1\n"
    "                    )\n"
    "                    r_total_mp = refl_total_mp[bin_idx_mp]\n"
    "                    t_total_mp = trans_total_mp[bin_idx_mp]\n"
    "                    rt_sum_mp = r_total_mp + t_total_mp\n"
    "                    roll_mp = rng.random(len(hit_idx))\n"
    "                    p_refl_mp = np.where(rt_sum_mp > 0, r_total_mp / np.maximum(rt_sum_mp, 1e-12), 1.0)\n"
    "                    refl_bsdf_mp = roll_mp < p_refl_mp\n"
    "                    trans_bsdf_mp = ~refl_bsdf_mp\n"
)

if old in content:
    content = content.replace(old, new, 1)
    open('backlight_sim/sim/tracer.py', 'w', encoding='utf-8').write(content)
    print('MP BSDF ABSORPTION FIXED')
else:
    print('NOT FOUND')
    idx = content.find('# BSDF dispatch')
    print(repr(content[idx:idx+600]))
