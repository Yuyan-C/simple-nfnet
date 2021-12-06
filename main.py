import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
import argparse
from model import NFNet
from optim import SGD_AGC
import time
import numpy as np


# Hyper-parameters
parser = argparse.ArgumentParser(description='NFNet Training')
parser.add_argument('--variant', default='F0', type=str, choices=['F0', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7'],
                    help='NFNet variants')
parser.add_argument('--lr', default=0.1, type=float, help='the learning rate')
parser.add_argument('--num_epochs', default=100, type=int, help='the number of the epochs')
parser.add_argument('--batch_size', default=128, type=int, help='batch sizes')
args = parser.parse_args()

# Device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
best_acc = 0

# Image preprocessing modules
transform_train = transforms.Compose([
    transforms.Pad(4),
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010))])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010))])

# CIFAR-10 dataset
train_dataset = torchvision.datasets.CIFAR10(root='./data/', train=True, transform=transform_train, download=True)

test_dataset = torchvision.datasets.CIFAR10(root='./data/', train=False, transform=transform_test)

# Data loader
train_loader = torch.utils.data.DataLoader(dataset=train_dataset, batch_size=args.batch_size, shuffle=True,
                                           num_workers=2)

test_loader = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=args.batch_size, shuffle=False,
                                          num_workers=2)

# Model
model = NFNet(num_classes=10, variant=args.variant, stochdepth_rate=0.25, alpha=0.2, se_ratio=0.5,
              activation='gelu').to(device)

# Loss and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = SGD_AGC(named_params=model.named_parameters(), lr=args.lr, momentum=0.9, clipping=0.1, weight_decay=5e-4,
                    nesterov=True)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200)


# Train the model
def train(epoch):
    model.train()
    for i, (images, labels) in enumerate(train_loader):
        images, labels = images.to(device), labels.to(device)

        # Forward pass
        outputs = model(images)
        loss = criterion(outputs, labels)

        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # if (i + 1) % 100 == 0:
        #     print(
        #         "Epoch [{}/{}], Step [{}/{}] Loss: {:.4f}".format(epoch + 1, args.num_epochs, i + 1, len(train_loader),
        #                                                           loss.item()))


# Test the model
def accuracy(data_loader):
    global best_acc
    model.eval()
    with torch.no_grad():
        correct = 0
        total = 0
        for images, labels in data_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    acc = 100 * correct / total
    # if mode == 'validation':
    #     if acc > best_acc:
    #         # Save the model checkpoint
    #         torch.save(model.state_dict(), 'nfnet.ckpt')
    #         best_acc = acc
    #         print('Best Accuracy : {} %'.format(best_acc))
    #
    return acc

records = []
for epoch in range(args.num_epochs):
    training_start_time = time.time()
    train(epoch)
    training_time = time.time() - training_start_time
    training_accuracy = accuracy(train_loader)
    validation_accuracy = accuracy(test_loader)

    print(f'Epoch[{epoch+1}/{len(range(args.num_epochs))}], '
          f'training accuracy: {training_accuracy}, validation accuracy: {validation_accuracy}, training time: {training_time}')
    if validation_accuracy > best_acc:
        torch.save(model.state_dict(), 'nfnet.ckpt')
        best_acc = validation_accuracy
    scheduler.step()
    records.append([training_time, training_accuracy, validation_accuracy])

records = np.array(records)
np.save(f'{args.variant}_records.npy', records)
