# Thanks to Shivam Thakkar
# https://buzzrobot.com/dominant-colors-in-an-image-using-k-means-clustering-3c7af4622036

from sklearn.cluster import KMeans
import cv2
import numpy as np
from skimage import io
from skimage.color import lab2rgb
import colour

def lab_to_rgb(color):
    r, g, b = color[0], color[1], color[2]
    lab = [[[r, g, b]]]
    rgb = lab2rgb(lab)
    rgb_parsed = str(rgb)[3:-3].split()
    rgb_floats = [float(i) for i in rgb_parsed]
    return [int(i * 255) for i in rgb_floats]

def dominant_colors(image, clusters=5):

    img = np.frombuffer(image, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_UNCHANGED)

    #convert to lab colorspace from bgr
    img = cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)

    #reshaping to a list of pixels
    img = img.reshape((img.shape[0] * img.shape[1], 3))

    #using k-means to cluster pixels, use a fixed random state so as to not get
    #different results from the same album if the clusters are close
    cluster = KMeans(n_clusters = clusters, tol=0.001, random_state=42)
    cluster.fit(img)

    #the cluster centers are our dominant colors.
    colors = cluster.cluster_centers_
    labels = cluster.labels_

    #for each label, find the percentage of the cluster centers the label 
    #consistutes
    labels = list(labels)
    percent = []
    for i in range(len(colors)):
        j = labels.count(i)
        j = j / (len(labels))
        percent.append(j)
    
    #sort the colors in descending order based on frequency
    percent = np.array(percent)
    colors = colors[(-percent).argsort()] 

    counter = 1
    primary = colors[0]
    secondary = colors[counter]

    highest_delta_e_counter = 1
    delta_e = colour.difference.delta_E_CIE2000(primary, secondary)
    highest_delta_e = delta_e

    # if difference between primary and secondary is perceptively too small,
    # loop through the rest of our color options in order until we find
    # one that is either over 20 delta E difference or fall back to the original
    if delta_e < 20:
        while (delta_e < 20 and counter < 4):
            counter += 1
            secondary = colors[counter]
            delta_e = colour.difference.delta_E_CIE2000(primary, secondary)
            if delta_e > highest_delta_e:
                highest_delta_e = delta_e
                highest_delta_e_counter = counter
    secondary = colors[highest_delta_e_counter]

    #convert back to rgb
    primary = lab_to_rgb(primary)
    secondary = lab_to_rgb(secondary)

    return primary, secondary