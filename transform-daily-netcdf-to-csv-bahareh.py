#!/usr/bin/python
# -*- coding: UTF-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. */

# Authors:
# Michael Berg-Mohnicke <michael.berg@zalf.de>
#
# Maintainers:
# Currently maintained by the authors.
#
# This file has been created at the Institute of
# Landscape Systems Analysis at the ZALF.
# Copyright (C: Leibniz Centre for Agricultural Landscape Research (ZALF)

import time
import os
import math
import json
import csv
from datetime import date, datetime, timedelta
from collections import defaultdict
import sys

from netCDF4 import Dataset
import numpy as np
#import numpy.ma as ma
from scipy.interpolate import NearestNDInterpolator
from pyproj import Proj, Transformer

LOCAL_RUN = True

def transform_netcdfs():

    config = {
        "basepath_to_data": "/beegfs/common/data/climate/dwd/cmip_cordex_reklies/",
        "netcdfs": "netcdfs/",
        "csvs": "csv/",
        "gcm": None,
        "rcm": None,
        "scen": None,
        "ensmem": None, #ensemble member = r<run_id>i1p1
        "version": None,
        "start_y": "1",
        "end_y": None,
        "start_x": "1", 
        "end_x": None, 
        "start_year": None,
        "end_year": None,
    }
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            kkk, vvv = arg.split("=")
            if kkk in config:
                config[kkk] = vvv
    
    path_to_netcdfs = config["basepath_to_data"] + config["netcdfs"]
    path_to_csvs = config["basepath_to_data"] + config["csvs"]

    elem_to_varname = {
        "tasmax": "tasmaxAdjustInterp",
        "tas": "tasAdjustInterp",
        "tasmin": "tasminAdjustInterp",
        "pr": "prAdjustInterp",
        "hurs": "hursAdjustInterp",
        "rsds": "rsdsAdjustInterp",
        "sfcWind": "sfcWindAdjustInterp"
    }

    files = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))))
    for d1 in os.listdir(path_to_netcdfs):
        path_1 = path_to_netcdfs + d1
        if d1.startswith("-"):
            continue

        if os.path.isdir(path_1):
            gcm, scen, _1, rcm, version = str(d1).split("_")

            elems = set(elem_to_varname.keys())
            for d2 in os.listdir(path_1):
                path_2 = path_1 + "/" + d2
                if os.path.isdir(path_2):
                    elem = str(d2)
                    elems.remove(elem)

                    for f in os.listdir(path_2):
                        path_3 = path_2 + "/" + f
                        if os.path.isfile(path_3):
                            _var, _2, _gcm, _scen, ensemble_member, _rcm, _incl_full_time_range, _3, _4, incl_time_range = str(f).split("_")
                            starty, endy = incl_time_range[:-3].split("-")
                            start_year = int(starty[:4])
                            end_year = int(endy[:4])
                            files[gcm][rcm][scen][ensemble_member][version][elem].append([start_year, end_year, path_3])
                            files[gcm][rcm][scen][ensemble_member][version][elem].sort()

            if len(elems) > 0:
                print(path_1, str(elems), "missing")


    def write_files(cache, nrows, gcm, rcm, scen, ensmem, version):
        "write files"

        no_of_files = len(cache)
        count = 0
        for (y, x), rows in cache.items():
            path_to_outdir = path_to_csvs + gcm + "/" + rcm + "/" + scen + "/" + ensmem + "/" + version + "/" + "row-" + str(nrows - y - 1) + "/"
            if not os.path.isdir(path_to_outdir):
                os.makedirs(path_to_outdir)

            path_to_outfile = path_to_outdir + "col-" + str(x) + ".csv"
            if not os.path.isfile(path_to_outfile):
                with open(path_to_outfile, "w", newline="") as _:
                    writer = csv.writer(_, delimiter=",")
                    writer.writerow(["iso-date", "tmin", "tavg", "tmax", "precip", "relhumid", "globrad", "windspeed"])
                    writer.writerow(["[]", "[°C]", "[°C]", "[°C]", "[mm]", "[%]", "[MJ m-2]", "[m s-1]"])

            with open(path_to_outfile, "a", newline="") as _:
                writer = csv.writer(_, delimiter=",")
                for row in rows:
                    writer.writerow(row)

            count = count + 1
            if count % 1000 == 0:
                print(count, "/", no_of_files, "written")


    wgs84 = Proj(init="epsg:4326")
    gk5 = Proj(init="epsg:31469")
    transformer = Transformer.from_proj(wgs84, gk5) 

    def create_elem_interpolator(elem_arr, lat_arr, lon_arr, wgs84, gk5):
        "read an ascii grid into a map, without the no-data values"

        points = []
        values = []

        nrows = elem_arr.shape[0]
        ncols = elem_arr.shape[1]
        
        for row in range(nrows):
            for col in range(ncols):
                if elem_arr.mask[row, col]: 
                    continue
                lat = lat_arr[row, col]
                lon = lon_arr[row, col]
                r_gk5, h_gk5 = transformer.transform(lon, lat)
                points.append([r_gk5, h_gk5])
                values.append((row, col))
                #print "row:", row, "col:", col, "lat:", lat, "lon:", lon, "val:", values[i]
            #print row,

        return NearestNDInterpolator(points, values)


    write_rows_threshold = 1
    for gcm, rest1 in files.items():
        if config["gcm"] and gcm != config["gcm"]:
            continue

        for rcm, rest2 in rest1.items():
            if config["rcm"] and rcm != config["rcm"]:
                continue

            for scen, rest3 in rest2.items():
                if config["scen"] and scen != config["scen"]:
                    continue

                for ensmem, rest4 in rest3.items():
                    if config["ensmem"] and ensmem != config["ensmem"]:
                        continue

                    for version, rest5 in rest4.items():
                        if config["version"] and version != config["version"]:
                            continue

                        interpol_cache = {}
                        time_range_count = len(rest5["tas"])
                        for time_range_index in range(time_range_count):
                            print("gcm:", gcm, "rcm:", rcm, "scen:", scen, "ensmem:", ensmem, "v:", version, "time_range_index:", time_range_index)
                            
                            start_years = set()
                            end_years = set()
                            #find smallest common denominator for start/end year
                            for elem, rest6 in rest5.items():
                                starty, endy, _ = rest6[time_range_index]
                                start_years.add(starty)
                                end_years.add(endy)
                            
                            start_year, end_year = (list(start_years)[-1], list(end_years)[0])
                            if config["start_year"] and start_year < int(config["start_year"]):
                                continue

                            data = {}
                            time_offsets = {}
                            time_shapes = {}
                            base_time_offset = 0
                            base_no_of_days = 0
                            ref_elem = "tas"
                            rsds_interpolate = None
                            datasets = []
                            #open all files for the first time range
                            for elem, rest6 in rest5.items():
                                _, _, file_path = rest6[time_range_index]

                                ds = Dataset(file_path)
                                datasets.append(ds)

                                data[elem] = ds.variables[elem_to_varname[elem]]
                                time_offsets[elem] = int(ds.variables["time"][0])
                                time_shapes[elem] = ds.variables["time"].shape[0]

                                # take tas as reference data
                                if elem == ref_elem:
                                    base_time_offset = int(ds.variables["time"][0])
                                    base_no_of_days = ds.variables["time"].shape[0]

                                if elem == "rsds":
                                    data["lat"] = ds.variables["lat"]
                                    data["lon"] = ds.variables["lon"]
                                    rsds_interpolate = create_elem_interpolator(data["rsds"][400], data["lat"], data["lon"], wgs84, gk5)


                            no_of_days = base_no_of_days
                            # set the time offsets for the grids, especially rsds
                            for elem, offset in time_offsets.items():
                                offset_ = abs(offset - base_time_offset)
                                nods = time_shapes[elem] - offset_
                                if nods < no_of_days:
                                    no_of_days = nods
                                time_offsets[elem] = offset_


                            ref_data = data[ref_elem][0] 
                            rsds_ref = data["rsds"][0]  
                            #no_of_days = ref_data.shape[0]
                            nrows = ref_data.shape[0]
                            ncols = ref_data.shape[1]

                            cache = defaultdict(list)
                            for y in range(int(config["start_y"]) - 1, int(config["end_y"]) if config["end_y"] else nrows):
                                #print("y: ", y, "->", flush=True)
                                start_time_y = time.clock()
                                #print(y, end=" ", flush=True)
                                
                                data_col_count = 0
                                for x in range(int(config["start_x"]) - 1, int(config["end_x"]) if config["end_x"] else ncols):
                                
                                    if ref_data[y, x] is np.ma.masked:
                                        #print(".", end=" ")#, flush=True)
                                        continue

                                    data_col_count += 1    
                                    #print(x, end=" ")#, flush=True)

                                    # for some reason the rsds data don't fit exactly to the other 6 variables,
                                    # but the datacells have the same lat/lon, so if a valid ref_data cell has 
                                    # no data in an rsds data cell, we choose the closest rsds cell
                                    interpol_rsds = rsds_ref[y, x] is np.ma.masked
                                    if interpol_rsds:
                                        if (y, x) in interpol_cache:
                                            closest_row, closest_col = interpol_cache[(y, x)]
                                        else:
                                            lat = data["lat"][y, x]
                                            lon = data["lon"][y, x]
                                            r_gk5, h_gk5 = transformer.transform(lon, lat)
                                            closest_row, closest_col = rsds_interpolate(r_gk5, h_gk5)
                                            interpol_cache[(y, x)] = (closest_row, closest_col)
                                    
                                    for i in range(no_of_days):
                                        if interpol_rsds:
                                            rsds = data["rsds"][i + time_offsets["rsds"], closest_row, closest_col]
                                        else:
                                            rsds = data["rsds"][i + time_offsets["rsds"], y, x]
                                        pr = round(data["pr"][i + time_offsets["pr"], y, x] * 60*60*24, 1)
                                        #if pr > 100:
                                        #    print("gcm:", gcm, "rcm:", rcm, "scen:", scen, "tri:", time_range_index, "y:", y, "x:", x, "pr:", pr, flush=True)
                                        row = [
                                            (date(start_year, 1, 1)+timedelta(days=i)).strftime("%Y-%m-%d"),
                                            str(round(data["tasmin"][i + time_offsets["tasmin"], y, x] - 273.15, 2)),
                                            str(round(data["tas"][i + time_offsets["tas"], y, x] - 273.15, 2)),
                                            str(round(data["tasmax"][i + time_offsets["tasmax"], y, x] - 273.15, 2)),
                                            str(pr),
                                            str(round(data["hurs"][i + time_offsets["hurs"], y, x], 1)),
                                            str(round(rsds * 60 * 60 * 24 / 1000000, 4)),
                                            str(round(data["sfcWind"][i + time_offsets["sfcWind"], y, x], 1))
                                        ]
                                        cache[(y,x)].append(row)

                                end_time_y = time.clock()
                                s_per_row = int(end_time_y - start_time_y)
                                print("row:", y, "|", s_per_row, "s | s/col:", s_per_row/data_col_count if data_col_count > 0 else "-", flush=True)
                            
                                if y > int(config["start_y"]) and y % write_rows_threshold == 0:
                                    s = time.clock()
                                    write_files(cache, nrows, gcm, rcm, scen, ensmem, version)
                                    cache = defaultdict(list)
                                    e = time.clock()
                                    print("wrote", write_rows_threshold, "ys in", (e-s), "seconds", flush=True)

                            print(flush=True)

                            #write remaining cache items
                            write_files(cache, nrows, gcm, rcm, scen, ensmem, version)

                            for ds in datasets:
                                ds.close()


if __name__ == "__main__":
    transform_netcdfs()