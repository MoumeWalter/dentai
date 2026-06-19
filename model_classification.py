from torchvision import datasets, transforms
from torch.utils.data import DataLoader, random_split
import torch
import torch.nn as nn
from torchvision import models
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt


# Transformations appliquées à chaque image
transform = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5], std=[0.5])
])

# Charger le dataset
dataset = datasets.ImageFolder(
    root=r"C:\Users\walte\OneDrive\Documents\Projects\dentai\Gold_Data\classification",
    transform=transform
)

print(f"Classes : {dataset.classes}")
print(f"Total images : {len(dataset)}")

total = len(dataset)
train_size = int(0.7 * total)
val_size = int(0.15 * total)
test_size = total - train_size - val_size

train_set, val_set, test_set = random_split(dataset, [train_size, val_size, test_size])

val_loader   = DataLoader(val_set,   batch_size=32, shuffle=False)
test_loader  = DataLoader(test_set,  batch_size=32, shuffle=False)

# Compter les images par classe
targets = torch.tensor(dataset.targets)
class_counts = np.bincount(targets)
print(f"Images par classe : {class_counts}")

# Calculer le poids de chaque classe
class_weights = 1.0 / class_counts

# Assigner un poids à chaque image selon sa classe
sample_weights = class_weights[targets]

# Créer le sampler
from torch.utils.data import WeightedRandomSampler
sampler = WeightedRandomSampler(
    weights=sample_weights[train_set.indices],
    num_samples=train_size,
    replacement=True
)

# Remplacer le train_loader par un loader avec sampler
train_loader = DataLoader(train_set, batch_size=32, sampler=sampler)

# Charger ResNet18 pré-entraîné
model = models.resnet18(weights='IMAGENET1K_V1')

# Adapter la dernière couche pour nos 5 classes
# conv1 original : attend 3 canaux (RGB)
# conv1 modifié  : attend 1 canal (niveaux de gris)
model.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)

# Adapter fc avec Dropout
num_features = model.fc.in_features  # ← avant de remplacer fc !
model.fc = nn.Sequential(
    nn.Dropout(0.5),
    nn.Linear(num_features, 5)
)

#                        ↑
#                    1 canal = niveaux de gris

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

NUM_EPOCHS = 10
best_val_acc = 0

for epoch in range(NUM_EPOCHS):
    model.train()
    train_loss = 0
    correct = 0
    
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item()
        correct += (outputs.argmax(1) == labels).sum().item()
    
    train_acc = correct / train_size
    # Validation
    model.eval()
    val_correct = 0
    
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            val_correct += (outputs.argmax(1) == labels).sum().item()
    
    val_acc = val_correct / val_size
    print(f"Epoch {epoch+1}/{NUM_EPOCHS} — Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, Val Acc: {val_acc:.4f}")
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), "best_model.pth")
        print(f"  → Meilleur modèle sauvegardé ! Val Acc: {val_acc:.4f}")


# Charger le meilleur modèle
model.load_state_dict(torch.load("best_model.pth"))
model.eval()

# Évaluation sur le test set
all_preds = []
all_labels = []

with torch.no_grad():
    for images, labels in test_loader:
        images = images.to(device)
        outputs = model(images)
        preds = outputs.argmax(1)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.numpy())

# Rapport de classification
print("\n=== Rapport de classification ===")
print(classification_report(
    all_labels,
    all_preds,
    target_names=dataset.classes
))

# Matrice de confusion
cm = confusion_matrix(all_labels, all_preds)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d',
            xticklabels=dataset.classes,
            yticklabels=dataset.classes)
plt.title("Matrice de confusion")
plt.ylabel("Vraie classe")
plt.xlabel("Classe prédite")
plt.tight_layout()
plt.savefig("confusion_matrix.png")
print("Matrice de confusion sauvegardée !")

print(f"\nMeilleure Val Acc obtenue : {best_val_acc:.4f}")
print(f"Modèle sauvegardé : best_model.pth")