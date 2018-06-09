# -*- coding: utf-8 -*-
import numpy as np
import pickle
import torch
import torch.autograd as autograd
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable
from torch.utils.data import Dataset, DataLoader


use_cuda = torch.cuda.is_available()




class WideDeepLoader(Dataset):
    """Helper to facilitate loading the data to the pytorch models.
    Parameters:
    --------
    data: namedtuple with 3 elements - (wide_input_data, deep_inp_data, target)
    """
    def __init__(self, data):

        self.X_wide = data.wide
        self.X_deep = data.deep
        self.Y = data.labels

    def __getitem__(self, idx):

        xw = self.X_wide[idx]
        xd = self.X_deep[idx]
        y  = self.Y[idx]

        return xw, xd, y

    def __len__(self):
        return len(self.Y)


class WideDeep(nn.Module):

    def __init__(self,
                 wide_dim,
                 embeddings_input,
                 continuous_cols,
                 deep_column_idx,
                 hidden_layers,
                 dropout,
                 encoding_dict):

        super(WideDeep, self).__init__()
        self.wide_dim = wide_dim
        self.deep_column_idx = deep_column_idx
        self.embeddings_input = embeddings_input
        self.continuous_cols = continuous_cols
        self.hidden_layers = hidden_layers
        self.dropout = dropout
        self.encoding_dict = encoding_dict

        # Build the embedding layers to be passed through the deep-side
        for col,val,dim in self.embeddings_input:
            setattr(self, 'emb_layer_'+col, nn.Embedding(val, dim))

        # Build the deep-side hidden layers with dropout if specified
        input_emb_dim = np.sum([emb[2] for emb in self.embeddings_input])
        self.linear_1 = nn.Linear(input_emb_dim+len(continuous_cols), self.hidden_layers[0])
        if self.dropout:
            self.linear_1_drop = nn.Dropout(self.dropout[0])
        for i,h in enumerate(self.hidden_layers[1:],1):
            setattr(self, 'linear_'+str(i+1), nn.Linear( self.hidden_layers[i-1], self.hidden_layers[i] ))
            if self.dropout:
                setattr(self, 'linear_'+str(i+1)+'_drop', nn.Dropout(self.dropout[i]))

        # Connect the wide- and dee-side of the model to the output neuron
        self.output = nn.Linear(self.hidden_layers[-1]+self.wide_dim, 1)


    def forward(self, X_w, X_d):

        # Deep Side
        emb = [getattr(self, 'emb_layer_'+col)(X_d[:,self.deep_column_idx[col]].long())
               for col,_,_ in self.embeddings_input]
        if self.continuous_cols:
            cont_idx = [self.deep_column_idx[col] for col in self.continuous_cols]
            cont = [X_d[:, cont_idx].float()]
            deep_inp = torch.cat(emb+cont, 1)
        else:
            deep_inp = torch.cat(emb, 1)

        x_deep = F.relu(self.linear_1(deep_inp))
        if self.dropout:
            x_deep = self.linear_1_drop(x_deep)
        for i in range(1,len(self.hidden_layers)):
            x_deep = F.relu( getattr(self, 'linear_'+str(i+1))(x_deep) )
            if self.dropout:
                x_deep = getattr(self, 'linear_'+str(i+1)+'_drop')(x_deep)

        # Deep + Wide sides
        wide_deep_input = torch.cat([x_deep, X_w.float()], 1)

        out = self.output(wide_deep_input)

        return out


# Network set up
wide_dim = wd_dataset['train_dataset'].wide.shape[1]
deep_column_idx = wd_dataset['deep_column_idx']
continuous_cols = wd_dataset['continuous_cols']

embeddings_input= wd_dataset['embeddings_input']
embeddings_input2 = embeddings_input[:18]
add_continuous = embeddings_input[18:]
continuous_cols2 = continuous_cols + [c[0] for c in add_continuous]
encoding_dict   = wd_dataset['encoding_dict']
hidden_layers = [100,50]
dropout = [0.5,0.2]

model = WideDeep(wide_dim,embeddings_input2,continuous_cols2,deep_column_idx,hidden_layers,dropout,encoding_dict)

train_dataset = wd_dataset['train_dataset']
widedeep_dataset = WideDeepLoader(train_dataset)
train_loader = DataLoader(dataset=widedeep_dataset,
    batch_size=64,
    shuffle=True)

model.cuda()
criterion = F.mse_loss
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
for i, (X_wide, X_deep, target) in enumerate(train_loader):
    if i < 10:
        X_w = Variable(X_wide)
        X_d = Variable(X_deep)
        y = Variable(target).float()
    else:
        break

    if use_cuda:
        X_w, X_d, y = X_w.cuda(), X_d.cuda(), y.cuda()

optimizer.zero_grad()
y_pred =  model(X_w, X_d)
loss = criterion(y_pred.squeeze(1), y)
loss.backward()
optimizer.step()

# print('Epoch {} of {}, Loss: {}'.format(epoch+1, n_epochs,
#     round(loss.data[0],3)))





    # def fit(self, dataset, n_epochs, batch_size):
    #     """Run the model for the training set at dataset.
    #     Parameters:
    #     ----------
    #     dataset (dict): dictionary with the training sets -
    #     X_wide_train, X_deep_train, target
    #     n_epochs (int)
    #     batch_size (int)
    #     """
    #     widedeep_dataset = WideDeepLoader(dataset)
    #     train_loader = torch.utils.data.DataLoader(dataset=widedeep_dataset,
    #                                                batch_size=batch_size,
    #                                                shuffle=True)

    #     # set the model in training mode
    #     net = self.train()
    #     for epoch in range(n_epochs):
    #         total=0
    #         correct=0
    #         for i, (X_wide, X_deep, target) in enumerate(train_loader):
    #             X_w = Variable(X_wide)
    #             X_d = Variable(X_deep)
    #             y = (Variable(target).float() if self.method != 'multiclass' else Variable(target))

    #             if use_cuda:
    #                 X_w, X_d, y = X_w.cuda(), X_d.cuda(), y.cuda()

    #             self.optimizer.zero_grad()
    #             y_pred =  net(X_w, X_d)
    #             loss = self.criterion(y_pred, y)
    #             loss.backward()
    #             self.optimizer.step()

    #             if self.method != "regression":
    #                 total+= y.size(0)
    #                 if self.method == 'logistic':
    #                     y_pred_cat = (y_pred > 0.5).squeeze(1).float()
    #                 if self.method == "multiclass":
    #                     _, y_pred_cat = torch.max(y_pred, 1)
    #                 correct+= float((y_pred_cat == y).sum().data[0])

    #         if self.method != "regression":
    #             print ('Epoch {} of {}, Loss: {}, accuracy: {}'.format(epoch+1,
    #                 n_epochs, round(loss.data[0],3), round(correct/total,4)))
    #         else:
    #             print ('Epoch {} of {}, Loss: {}'.format(epoch+1, n_epochs,
    #                 round(loss.data[0],3)))


    # def predict(self, dataset):
    #     """Predict target for dataset.
    #     Parameters:
    #     ----------
    #     dataset (dict): dictionary with the testing dataset -
    #     X_wide_test, X_deep_test, target
    #     Returns:
    #     --------
    #     array-like with the target for dataset
    #     """

    #     X_w = Variable(torch.from_numpy(dataset.wide)).float()
    #     X_d = Variable(torch.from_numpy(dataset.deep))

    #     if use_cuda:
    #         X_w, X_d = X_w.cuda(), X_d.cuda()

    #     # set the model in evaluation mode so dropout is not applied
    #     net = self.eval()
    #     pred = net(X_w,X_d).cpu()
    #     if self.method == "regression":
    #         return pred.squeeze(1).data.numpy()
    #     if self.method == "logistic":
    #         return (pred > 0.5).squeeze(1).data.numpy()
    #     if self.method == "multiclass":
    #         _, pred_cat = torch.max(pred, 1)
    #         return pred_cat.data.numpy()


    # def predict_proba(self, dataset):
    #     """Predict predict probability for dataset.
    #     This method will only work with method logistic/multiclass
    #     Parameters:
    #     ----------
    #     dataset (dict): dictionary with the testing dataset -
    #     X_wide_test, X_deep_test, target
    #     Returns:
    #     --------
    #     array-like with the probability for dataset.
    #     """

    #     X_w = Variable(torch.from_numpy(dataset.wide)).float()
    #     X_d = Variable(torch.from_numpy(dataset.deep))

    #     if use_cuda:
    #         X_w, X_d = X_w.cuda(), X_d.cuda()

    #     # set the model in evaluation mode so dropout is not applied
    #     net = self.eval()
    #     pred = net(X_w,X_d).cpu()
    #     if self.method == "logistic":
    #         pred = pred.squeeze(1).data.numpy()
    #         probs = np.zeros([pred.shape[0],2])
    #         probs[:,0] = 1-pred
    #         probs[:,1] = pred
    #         return probs
    #     if self.method == "multiclass":
    #         return pred.data.numpy()


    # def get_embeddings(self, col_name):
    #     """Extract the embeddings for the embedding columns.
    #     Parameters:
    #     -----------
    #     col_name (str) : column we want the embedding for
    #     Returns:
    #     --------
    #     embeddings_dict (dict): dictionary with the column values and the embeddings
    #     """

    #     params = list(self.named_parameters())
    #     emb_layers = [p for p in params if 'emb_layer' in p[0]]
    #     emb_layer  = [layer for layer in emb_layers if col_name in layer[0]][0]
    #     embeddings = emb_layer[1].cpu().data.numpy()
    #     col_label_encoding = self.encoding_dict[col_name]
    #     inv_dict = {v:k for k,v in col_label_encoding.iteritems()}
    #     embeddings_dict = {}
    #     for idx,value in inv_dict.iteritems():
    #         embeddings_dict[value] = embeddings[idx]

    #     return embeddings_dict