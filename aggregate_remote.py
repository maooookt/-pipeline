
import os
import re
import pandas as pd
import numpy as np
import subprocess

def parse_charmm_energies(log_lines):
    vdw, coul, gbenr = np.nan, np.nan, np.nan
    for line in log_lines:
        if "LAVE EXTERN>" in line:
            parts = line.split()
            vdw, coul = float(parts[2]), float(parts[3])
        elif "LAVE PBEQ>" in line:
            parts = line.split(); gbenr = float(parts[4])
    return vdw, coul, gbenr

start_id, end_id = 801, 900
search_date = "*"
base_dir = "/home/teraimao/experiment/confirm/"
output_path = "/home/teraimao/experiment/confirm/master_database_server_side.csv"

valid_pattern = re.compile(r"^(\d+)_(\d{4}.\d{2}.\d{2})_(\d+)ps_work$")
results = []

print(f"Server-side processing started: ID {start_id} to {end_id}")

for seq_id in range(start_id, end_id + 1):
    folders = subprocess.getoutput(f"ls -d {base_dir}{seq_id}_{search_date}_*ps_work 2>/dev/null").splitlines()
    for path in folders:
        folder_name = os.path.basename(path)
        match = valid_pattern.match(folder_name)
        if not match: continue
        
        extracted_id = int(match.group(1))
        extracted_date = match.group(2)
        t_end_ps = float(match.group(3))
        expected = int(t_end_ps * 0.25)
        
        for pos in range(1, 6):
            pos_dir = f"{path}/gbsw_{pos}"
            
            # A. Z座標 (バックスラッシュを回避するためにシングルクォートを活用)
            z_coord = np.nan
            inp_path = f"{pos_dir}/charmm.inp"
            if os.path.exists(inp_path):
                # awkのクォーテーションを工夫してバックスラッシュを排除
                z_cmd = "grep 'refz' " + inp_path + " | awk '{for(i=1;i<=NF;i++) if($i==\"refz\") print $(i+1)}'"
                z_coord = subprocess.getoutput(z_cmd)

            # B. エネルギー
            vdw, coul, solv = np.nan, np.nan, np.nan
            log_path = f"{pos_dir}/log"
            if os.path.exists(log_path):
                lave_lines = subprocess.getoutput(f"grep -A 10 'LAVE>' {log_path}").splitlines()
                vdw, coul, solv = parse_charmm_energies(lave_lines)

            # C. 解析データ
            hb_path = f"{path}/analysis/ana_gbsw_{pos}/hbond/output.dat"
            hb_avg, hb_n = 0, 0
            if os.path.exists(hb_path):
                res = subprocess.getoutput("awk '{sum+=$2; n++} END {if(n>0) print sum/n, n; else print \"0 0\"}' " + hb_path).split()
                hb_avg, hb_n = (float(res[0]), int(res[1])) if len(res) >= 2 else (0, 0)

            sasa_path = f"{path}/analysis/ana_gbsw_{pos}/surf_area/sasa_{pos}.dat"
            sasa_avg, sasa_n = 0, 0
            if os.path.exists(sasa_path):
                res = subprocess.getoutput("awk '{sum+=$2; n++} END {if(n>0) print sum/n, n; else print \"0 0\"}' " + sasa_path).split()
                sasa_avg, sasa_n = (float(res[0]), int(res[1])) if len(res) >= 2 else (0, 0)

            status = "Success" if (hb_n >= expected and sasa_n >= expected) else "Failed"

            results.append({
                "ID": extracted_id, "Date": extracted_date, "Pos_Num": pos, "Z_Coord": z_coord,
                "t_end_ps": t_end_ps, "Status": status, "HB_Avg": hb_avg,
                "SASA_Avg": sasa_avg, "Solv_Free_Avg": solv, "vdW_Avg": vdw, "Coul_Avg": coul
            })
    if seq_id % 100 == 0:
        print(f"Processed ID: {seq_id}")

if results:
    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"DONE! Saved {len(results)} rows to {output_path}")
