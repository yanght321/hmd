from __future__ import print_function 
import sys
sys.path.append("../src/")
import numpy as np
import PIL.Image
import pickle
import json
from tqdm import trange
from time import sleep
import renderer as rd
from scipy.io import loadmat
from mesh_edit import fast_deform_dja
from mesh_edit import fast_deform_dsa
from hmr_predictor import hmr_predictor
from hmr_predictor import proc_sil
from utility import make_trimesh
from utility import get_joint_move
from utility import get_achr_move
from utility import get_anchor_posi
from data_filter import lsp_filter
from utility import take_notes

# first 1000 are train set, last 1000 are test set
def proc_lsp(train_dir, test_dir, train_id, test_id, lsp_dir, upi_dir):
    
    faces = np.load("../predef/smpl_faces.npy")
    face_num = len(faces)
    
    hmr_pred = hmr_predictor()
    renderer = rd.SMPLRenderer(face_path = 
                               "../predef/smpl_faces.npy")
    
    lsp_joints = loadmat(lsp_dir + "joints.mat")['joints']
    
    with open ('../predef/mesh_joint_list.pkl', 'rb') as fp:
        mesh_joint = pickle.load(fp)
    
    count_all = 0.
    count_work = 0.
    
    # make train set
    tr = trange(1000, desc='Bar desc', leave=True)
    for i in tr:
        tr.set_description("LSP - train part")
        tr.refresh() # to show immediately the update
        sleep(0.01)
        
        count_all += 1

        # read sil
        src_gt_sil = np.array(PIL.Image.open(
                     upi_dir + "lsp/im%04d_segmentation.png"%(i+1)))
        
        # judge using filter
        result = lsp_filter(lsp_joints[:,:,i], src_gt_sil)
        if result is False:
            take_notes("LSP %04d BAN -1\n" % (i+1), "./data_log.txt")
            continue
        
        # read ori img
        ori_img = np.array(PIL.Image.open(
                  lsp_dir + "images/im%04d.jpg"%(i+1)))

        # hmr predict
        verts, cam, proc_para, std_img = hmr_pred.predict(ori_img)
        
        # unnormalize std_img
        src_img = ((std_img+1).astype(np.float)/2.0*255).astype(np.uint8)
        
        # save img
        img_file = "img/LSP_%08d.png" % (i+1)
        PIL.Image.fromarray(src_img).save(train_dir + img_file)
        
        # process sil
        gt_sil = proc_sil(src_gt_sil, proc_para)

        # get proj sil
        proj_sil = renderer.silhouette(verts = verts,
                                       cam = cam,
                                       img_size = src_img.shape,
                                       norm = False)

        # make TriMesh
        mesh = make_trimesh(verts, faces, compute_vn = True)
        vert_norms = mesh.vertex_normals()

        # get joint move
        new_jv, _, joint_move, joint_posi = get_joint_move(verts, 
                                               lsp_joints[:,:,i], 
                                               proc_para,
                                               mesh_joint)
        joint_move = joint_move.flatten()

        # joint deform
        fd_ja = fast_deform_dja(weight = 10.0)
        ja_verts = fd_ja.deform(np.asarray(verts), new_jv)

        # get achr move
        proj_sil_ja = renderer.silhouette(verts = ja_verts,
                                       norm = False)

        _, achr_verts, achr_move = get_achr_move(gt_sil, 
                                                 ja_verts, 
                                                 vert_norms,
                                                 proj_sil_ja)
        achr_posi = get_anchor_posi(achr_verts)
        
        # save sil
        compose_sil = np.stack((gt_sil, proj_sil, proj_sil_ja))
        compose_sil = np.moveaxis(compose_sil, 0, 2)
        compose_sil = PIL.Image.fromarray(compose_sil.astype(np.uint8))
        compose_sil.save(train_dir + "sil/%08d.png" % train_id)

        # save para
        proc_para['end_pt'] = proc_para['end_pt'].tolist()
        proc_para['start_pt'] = proc_para['start_pt'].tolist()
        para = {"verts": verts.tolist(),
                "vert_norms": vert_norms.tolist(),
                "proc_para": proc_para,
                "joint_move": joint_move.tolist(),
                "joint_posi": joint_posi.tolist(),
                "achr_move": achr_move.tolist(),
                "achr_posi": achr_posi.tolist(),
                "img_file": img_file,
               }
        with open(train_dir + "para/%08d.json" % train_id, 'wb') as fp:
            json.dump(para, fp)
        
        take_notes("LSP %04d TRAIN %08d\n" % (i+1, train_id), "./data_log.txt")
        train_id += 1
        count_work += 1
    
        
    #make test set
    tr = trange(1000, desc='Bar desc', leave=True)
    for i in tr:
        tr.set_description("LSP - test part")
        tr.refresh() # to show immediately the update
        sleep(0.01)
        
        count_all += 1
        
        # read sil            
        src_gt_sil = np.array(PIL.Image.open(
                     upi_dir + "lsp/im%04d_segmentation.png"%(i+1001)))
        
        # judge using filter
        result = lsp_filter(lsp_joints[:,:,i], src_gt_sil)
        if result is False:
            take_notes("LSP %04d BAN -1\n" % (i+1), "./data_log.txt")
            continue
            
        # read ori img        
        ori_img = np.array(PIL.Image.open(
                  lsp_dir + "images/im%04d.jpg"%(i+1001)))
        
        # hmr predict
        verts, cam, proc_para, std_img = hmr_pred.predict(ori_img)
                
        # unnormalize std_img        
        src_img = ((std_img+1).astype(np.float)/2.0*255).astype(np.uint8)
        
        # save img
        img_file = "img/LSP_%08d.png" % (i+1001)
        PIL.Image.fromarray(src_img).save(test_dir + img_file)
        
        
        # process sil        
        gt_sil = proc_sil(src_gt_sil, proc_para)
        
        # get proj sil
        proj_sil = renderer.silhouette(verts = verts,
                                       cam = cam,
                                       img_size = src_img.shape,
                                       norm = False)

        # make TriMesh
        mesh = make_trimesh(verts, faces, compute_vn = True)
        vert_norms = mesh.vertex_normals()

        # get joint move
        new_jv, _, joint_move, joint_posi = get_joint_move(verts, 
                                               lsp_joints[:,:,i+1000], 
                                               proc_para,
                                               mesh_joint)
        joint_move = joint_move.flatten()

        # joint deform
        fd_ja = fast_deform_dja(weight = 10.0)
        ja_verts = fd_ja.deform(np.asarray(verts), new_jv)

        # get achr move
        proj_sil_ja = renderer.silhouette(verts = ja_verts,
                                       norm = False)
        _, achr_verts, achr_move = get_achr_move(gt_sil, 
                                                 ja_verts, 
                                                 vert_norms,
                                                 proj_sil_ja)
        achr_posi = get_anchor_posi(achr_verts)
        
        # save sil
        compose_sil = np.stack((gt_sil, proj_sil, proj_sil_ja))
        compose_sil = np.moveaxis(compose_sil, 0, 2)
        compose_sil = PIL.Image.fromarray(compose_sil.astype(np.uint8))
        compose_sil.save(test_dir + "sil/%08d.png" % test_id)

        proc_para['end_pt'] = proc_para['end_pt'].tolist()
        proc_para['start_pt'] = proc_para['start_pt'].tolist()
        # save para
        para = {"verts": verts.tolist(),
                "vert_norms": vert_norms.tolist(),
                "proc_para": proc_para,
                "joint_move": joint_move.tolist(),
                "joint_posi": joint_posi.tolist(),
                "achr_move": achr_move.tolist(),
                "achr_posi": achr_posi.tolist(),
                "img_file": img_file,
               }
        with open(test_dir + "para/%08d.json" % test_id, 'wb') as fp:
            json.dump(para, fp)

        take_notes("LSP %04d TEST %08d\n" % (i+1001, test_id), 
                   "./data_log.txt")
        test_id += 1
        count_work += 1
        
    print("work ratio = %f, (%d / %d)" 
          % (count_work/count_all, count_work, count_all))
    return train_id, test_id
