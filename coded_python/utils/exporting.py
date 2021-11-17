import ee
ee.Initialize()

# Export.table.toCloudStorage(collection, description, bucket, fileNamePrefix, fileFormat, selectors, maxVertices)
def export_table_cloud(collection:ee.FeatureCollection, description:str, bucket:str, fileNamePrefix:str, fileFormat:str, selectors:list, maxVertices:int=None):
    task = ee.batch.Export.table.toCloudStorage(collection=collection,description=description,bucket=bucket)
    task.start()
    return description
    
# Export.table.toAsset(collection, description, assetId, maxVertices)
def export_table_asset(collection:ee.FeatureCollection, description:str, assetId:str, maxVertices: int=None):
    task = ee.batch.Export.table.toAsset(collection, description, assetId, maxVertices)
    task.start()
    return description
    
def export_img(image,
               geometry,
               name,
               export_path,
               export_scale=30,
               crs=None,
               dry_run=False,
               test=False):

    export_path = export_path.strip('/')

    if dry_run:
        print(f'EXPORT NAME : {name}')
        print(f'EXPORT PATH : {export_path}/{name}')
        print(f"EXPORT SCALE : {export_scale}")
        print(f"EXPORT CRS : {crs}")

    else:
        if test:
            name = f"test_{name}"

        task = ee.batch.Export.image.toAsset(
            image=image, description=name,
            assetId=f'{export_path}/{name}',
            region=geometry.geometry(),
            scale=export_scale,
            crs=crs,
            maxPixels=1e13,
            pyramidingPolicy={'.default': 'sample'}
        )

        task.start()
        print(f'task started {name}')
    return name


def export_image_collection(collection, export_func, geometry=None, export_path=None, export_scale=None, crs=None, test=False):
    if geometry is None:
        geometry = geometry
    collection = collection.sort('system:time_start')
    col_size = collection.size()
    col_list = collection.toList(col_size)
    col_size_local = 12
    export_descriptions = []
    if test:
        col_size_local = 1
    for i in range(0, col_size_local):
        img_in = ee.Image(col_list.get(i))
        desc = export_func(img_in, geometry, i,
                           export_path, export_scale, crs, test)
        export_descriptions.append(desc)

    return export_descriptions
