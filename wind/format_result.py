import base64
import numpy as np
import math
from io import BytesIO
from PIL import Image

from wind.infrared import InfraredProject
from wind.data import convert_tif_to_geojson_features, get_south_west_corner_coords_of_bbox

def format_result(infrared_project: InfraredProject, result_type: str,  out_format: str):
    result = infrared_project.get_result_for(result_type)

    if not result["analysisOutputData"]:
        # empty result (e.g. not in ROI) -> return empty list of features
        return []

    # return array of geojson like features
    if out_format == "geojson":
        features = convert_tif_to_geojson_features(infrared_project.get_result_geotif_for(result_type))
        return features

    
    # return a geotiff
    if out_format == 'geotiff':
        bounds_polygon = infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        with open(infrared_project.get_result_geotif_for(result_type), "rb") as image_file:
            base64_bytes = base64.b64encode(image_file.read())
            base64_string = base64_bytes.decode('utf-8')

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "bbox_coordinates": bounds_coordinates,
            "image_base64_string": base64_string
        }]

    # return data as raw array
    if out_format == "raw":
        bounds_polygon =  infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "bbox_coordinates": bounds_coordinates,
            "values": result["analysisOutputData"]
        }]

    # return data as png (used for physical table)
    if out_format == "png":
        bounds_polygon = infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        image_data = result["analysisOutputData"]

        # convert image data to ints from 0-255 (for png)
        # set NaN as 0
        image_data = [
            [int(round(x * 255)) if not math.isnan(x) else 0 for x in image_line]
            for image_line in image_data
        ]
        # create a np array from image data
        np_values = np.array(image_data, dtype="uint8")

        # create a pillow image, save it and convert to base64 string
        im = Image.fromarray(np_values)
        output_buffer = BytesIO()
        im.save(output_buffer, format='PNG')
        byte_data = output_buffer.getvalue()
        base64_bytes = base64.b64encode(byte_data)
        base64_string = base64_bytes.decode('utf-8')

        img_width, img_height = im.size

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "img_width": img_width,
            "img_height": img_height,
            "bbox_coordinates": bounds_coordinates,
            "image_base64_string": base64_string
        }]

    else:
        print("unknown format requested: ", out_format)
        raise NotImplementedError
