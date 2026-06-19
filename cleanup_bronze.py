# Supprimer le dataset 2 (classes inconnues, non utilisé)
objects = client.list_objects(BUCKET_NAME, prefix="detection/dataset_opg/", recursive=True)
for obj in objects:
    client.remove_object(BUCKET_NAME, obj.object_name)
    
print("Dataset OPG Object Detection supprimé du bronze !")