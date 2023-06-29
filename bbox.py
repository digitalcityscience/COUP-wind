from wind.data import create_bbox_matrix
import geopandas
from shapely.geometry import Polygon
import matplotlib.pyplot as plt


if __name__ == "__main__":

    area_gdf = geopandas.read_file("wind/project_area_utm.geojson")
    area_pol = list(area_gdf.geometry)[0]

    bboxes_inner = create_bbox_matrix(area_pol, 460)


    boxes_inner_gdf = geopandas.GeoDataFrame(geometry=bboxes_inner)
    boxes_inner_gdf = boxes_inner_gdf.set_crs("EPSG:25832")
    boxes_outer_gdf = boxes_inner_gdf.buffer(40, cap_style=2)
    
    ax = area_gdf.plot(color='white', edgecolor='blue', alpha=1)
    ax = boxes_outer_gdf.plot(ax=ax, color='white', edgecolor='pink', alpha=0.5)
    #ax = boxes_inner_gdf.plot(ax=ax, color='white', edgecolor='pink')
    


    plt.show()