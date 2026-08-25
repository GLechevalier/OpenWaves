/**
 *   @file  caponBeamforming2D.c
 *
 *   @brief
 *      Implements 2D Capon Beamforming functionality.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2025 Gauthier Lechevalier
 *
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>

#include "caponBeamforming2D.h"

#define PI 3.14159265359

uint32_t gStart_time;
uint32_t gCalcul_matrice_covariance_t;
uint32_t gCalcul_inverse_matrice_cov_t;
uint32_t gCalcul_boucles_t;
uint32_t gCalcul_steering_vector_t;
uint32_t gCalcul_caponSpectrum_t;
uint32_t gEndTime;

void print_list_float1(float* list, int32_t size);
void print_list_double(double* list, int32_t size);

/**
 * BLOC DE FONCTIONS SERVANT A CALCULER LA MATRICE DE COVARIANCE DU SIGNAL
 */

void calculer_transconjugue(float* vecteur, int8_t taille, float* transconjugue) {
    /**
     * Fonction pour obtenir le transconjugu� d'un vecteur :
     *
     * vecteur :       vecteur � transconjuguer, ce dernier est de taille nx1 en complexe
     * taille :        taille du vecteur  n
     * transconjugue : pointeur vers le vecteur d'output
     *
     */

    for (int8_t j=0; j<taille; j++) {
        transconjugue[j*2] = vecteur[2*j];
        transconjugue[j*2+1] = -vecteur[2*j+1];
    }
    return ;
}

void get_k_row_from_X(int32_t* input, float* output, int16_t num_antennes, int8_t k) {
    /**
     * Fonction permettant de r�aliser X[k] en python, c'est � dire obtenir la ligne k d'une matrice
     * Subtilit� importante : la matrice �tant complexe, on obtient en sortie une matrice �galement
     * (et non un vecteur) : dim(X) = (32, 6, 2), dim(X[k]) = (6, 2)
     */
    memset((float*) &output[0], 0.0, 2*num_antennes*sizeof(float));
    int16_t index;
    for (int16_t j=0; j<num_antennes;j++) {
        index = j + k*num_antennes;
        output[2*j] = (float) input[2*index]; //Re
        output[2*j+1] = (float) input[2*index+1]; //Im
    }
    return;
}

void calculer_matrice_Xk_Xk_h(float* input, float* input_H, int8_t taille, float* output){
    /**
     * Fonction permettant de calculer la multiplication X[k] * X[k]^H (c'est � dire le vecteur complexe X[k]
     * multipli� par son transconjugu�, ce qui donne une nouvelle matrice complexe de taille (dim(X[k])[0], dim(X[k])[0])
     * ou bien une matrice r�elle de taille : (dim(X[k])[0], dim(X[k])[0], 2) = (6, 6, 2)
     */
    for (int8_t row=0; row<taille; row++){
        for (int8_t col=0; col<taille; col++) {
            // (a+ib)*(c+id) = ac-bd + i(bc+ad)
            float a = input[2*row];
            float b = input[2*row+1];
            float c = input_H[2*col];
            float d = input_H[2*col+1];

            // Re
            output[2*(col+row*taille)] += a*c - b*d;
            // Im
            output[2*(col+row*taille)+1] += b*c + a*d;
        }
    }
    return;
}

void normalize(float* input, int8_t taille, float N) {
    /**
     * Fonction permettant de normaliser une matrice carr�e (i.e. diviser tous les composants par N)
     */
    for (int8_t row=0; row<taille; row++){
        for (int8_t col=0; col<taille; col++) {
            input[2*(col+row*taille)] = input[2*(col+row*taille)]/N;
            input[2*(col+row*taille)+1] = input[2*(col+row*taille)+1]/N;
        }
    }
    return;
}


void calculer_matrice_de_covariance(int32_t* input, int8_t num_antennes, int16_t num_snapshots, float* R){
    /**
     * Cette fonction a pour objectif de calculer la matrice de covariance des num_antennes signaux qui sont disponibles
     * dans l'input � travers num_snapshots diff�rents. C'est un calcul bete et m�chant de corr�lation.
         * input : matrice (n_frames, n_antennes, 2)
         *      premier axe : frames diff�rentes,
         *      deuxi�me axe : antennes diff�rentes,
         *      troisi�me axe: r�el/imag
         *
         *      matrice[f][ant][ri] = matrice[ri + ant*2 + f*2*num_ant] = matrice[ri + 2*(ant+f*num_ant)]
         */


    float transconjugue[num_antennes*2];
    float vecteur_calcul[num_antennes*2];

    for (int16_t k=0; k<num_snapshots; k++){
        get_k_row_from_X(input, vecteur_calcul, num_antennes, k);
        calculer_transconjugue(vecteur_calcul, num_antennes, transconjugue);

        calculer_matrice_Xk_Xk_h(vecteur_calcul, transconjugue, num_antennes, R);
    }
    //print_list_double(R, 72);
    normalize(R, num_antennes, (float) num_snapshots);
    return;
}

/**
 * BLOC DE FONCTIONS SERVANT A INVERSER LA MATRICE DE COVARIANCE !!!
 */

void extraire_matrices_reelles_imaginaires_de_R(float* R, float* R_re, float* R_im, int8_t taille) {
    /**
     * Cette fonction a pour objectif de convertir R (de taille (6x6x2)) en deux matrices r�elles
     * et imaginaires chacunes de taille 6x6
     */
    for (int8_t row=0; row<taille; row++) {
        for (int8_t col=0; col<taille; col++) {
            R_re[col + taille*row] = R[2*(col+taille*row)];
            R_im[col + taille*row] = R[2*(col+taille*row)+1];
        }
    }
    return;
}

void complexe_vers_reel(float *A_re, float *A_im, float *A_12x12, int8_t n) {
    /**
     * Cette fonction transforme une matrice complexe (6x6) en matrice relle (12x12) tel que :
     * [[Re(A) -Im(A)]
     *  [Im(A)  Re(A)]]
     *
     */

    // Bloc sup�rieur gauche: Re(A)
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A_12x12[i * n*2 + j] = A_re[i * n + j];
        }
    }

    // Bloc sup�rieur droit: -Im(A)
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A_12x12[i * n*2 + (j + n)] = -A_im[i * n + j];
        }
    }

    // Bloc inf�rieur gauche: Im(A)
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A_12x12[(i + n) * n*2 + j] = A_im[i * n + j];
        }
    }

    // Bloc inf�rieur droit: Re(A)
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A_12x12[(i + n) * n*2 + (j + n)] = A_re[i * n + j];
        }
    }
}

int inverser_matrice_inplace(float *A, int n) {
    /**
     * Fonction permettant d'inverser une matrice de taille nxn
     */

    // Buffer statique pour �viter malloc
    float aug[n * n * 2]; //taille de [A | I]

    // Cr�er [A | I]
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            aug[i * 2*n + j] = A[i*n + j];
            aug[i * 2*n + n + j] = (i == j) ? 1.0f : 0.0f;
        }
    }

    // Gauss-Jordan
    for (int i = 0; i < n; i++) {
        // Trouver le pivot maximal
        int pivot = i;
        float max_val = fabsf(aug[i * 2*n + i]);
        for (int j = i + 1; j < n; j++) {
            float val = fabsf(aug[j * 2*n + i]);
            if (val > max_val) {
                max_val = val;
                pivot = j;
            }
        }

        if (max_val < 1e-6f) return -1;  // Singuli�re

        // �changer lignes
        if (pivot != i) {
            for (int j = 0; j < 2*n; j++) {
                float temp = aug[i * 2*n + j];
                aug[i * 2*n + j] = aug[pivot * 2*n + j];
                aug[pivot * 2*n + j] = temp;
            }
        }

        // Normaliser ligne pivot
        float div = aug[i * 2*n + i];
        for (int j = i; j < 2*n; j++) {  // Optimisation: commencer � i
            aug[i * 2*n + j] /= div;
        }

        // �liminer colonne
        for (int k = 0; k < n; k++) {
            if (k != i) {
                float factor = aug[k * 2*n + i];
                for (int j = i; j < 2*n; j++) {  // Optimisation: commencer � i
                    aug[k * 2*n + j] -= factor * aug[i * 2*n + j];
                }
            }
        }
    }

    // Copier r�sultat
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A[i*n + j] = aug[i * 2*n + n + j];
        }
    }

    return 0;
}

void reel_vers_complexe(float *A_12x12, float *A_re, float *A_im, int8_t n) {

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            A_re[i * n + j] = A_12x12[i * n*2 + j];
            A_im[i * n + j] = A_12x12[(i + n) * n*2 + j];
        }
    }
}

void build_r_inv(float* R_re, float* R_im, float* Rinv, int8_t taille) {
    for (int8_t row=0; row<taille; row++) {
        for (int8_t col=0; col<taille; col++) {
            Rinv[2*(col+taille*row)] = R_re[col + taille*row];
            Rinv[2*(col+taille*row)+1] = R_im[col + taille*row];
        }
    }
}

int inverser_matrice_de_covariance(float* R, int8_t taille_R, float* Rinv, float epsilon){
    /**
     * Cette fonction permet d'inverser R en Rinv.
     */

    float R_re[taille_R*taille_R];
    float R_im[taille_R*taille_R];
    float R_12x12[taille_R*2*taille_R*2];

    memset(R_re, 0, sizeof(float)*taille_R*taille_R);
    memset(R_im, 0, sizeof(float)*taille_R*taille_R);
    memset(R_12x12, 0, sizeof(float)*taille_R*2*taille_R*2);
    int retVal=0;

    extraire_matrices_reelles_imaginaires_de_R(R, R_re, R_im, taille_R);
    complexe_vers_reel(R_re, R_im, R_12x12, taille_R);
    //ajouter une r�gularisation si epsilon >0 pour am�liorer la stabilit� num�rique
    if (epsilon>0) {
        for (int8_t i=0; i<taille_R*2;i++) {
            R_12x12[i+taille_R*2*i] += (float) epsilon;
        }
    }
    retVal = inverser_matrice_inplace(R_12x12, taille_R*2);
    if (retVal < 0) {
        return -1;
    }
    reel_vers_complexe(R_12x12, R_re, R_im, taille_R);
    build_r_inv(R_re, R_im, Rinv, taille_R);

    return 0;
}

/**
 * BLOC DE FONCTION SERVANT A CALCULER LE STEERING VECTOR
 */


void get_pn(float* pn, int8_t n, uint8_t* antenna_pos_config) {

    float dist[] = {2.418, 2.418};

    pn[0] = antenna_pos_config[2*n+1]*dist[0];
    pn[1] = antenna_pos_config[2*n]*dist[1];

    return;
}

void calculer_steering_vector(float theta, float phi, float alpha, int8_t num_antennes, uint8_t* antennaCoordinates, float* a_theta_phi) {
    float psi_n;
    float pn[2];
    float lambda = 4.836;
    int8_t spheric=1;

    a_theta_phi[0] = 1.0;
    a_theta_phi[1] = 0.0;

    float f_theta, cos_phi, sin_phi;
    if (spheric==1) {
        f_theta = sinf(theta);
        cos_phi = cosf(phi);
        sin_phi = sinf(phi);
    } else {
        f_theta = 1;
        cos_phi = (theta)*cosf(alpha) + phi*sinf(alpha);
        sin_phi = -(theta)*sinf(alpha) + phi*cosf(alpha);
    }


    for (int8_t i=1; i<num_antennes;i++) {
        get_pn(pn, i, antennaCoordinates);

        psi_n = 2*PI/lambda*f_theta*(pn[0]*cos_phi+pn[1]*sin_phi);

        a_theta_phi[2*i] = cosf(psi_n);
        a_theta_phi[2*i +1] = sinf(psi_n);
    }
    return;
}

/**
 * BLOC DE FONCTIONS PERMETTANT DE CALCULER LES POIDS OPTIMAUX
 */

void calculer_spectre_capon(float* Rinv, float* a_theta_phi, int8_t num_antennes, float* re) {
    float normalisation_coeff_re = 0;
    float a_theta_phi_H[num_antennes*2];
    calculer_transconjugue(a_theta_phi, num_antennes, a_theta_phi_H);

    float a,b,c,d;

    float buffer[num_antennes*2];

    // Calculer Rinv * a_theta_phi
    for (int8_t i=0; i<num_antennes; i++) {
        buffer[2*i] = 0.0;
        buffer[2*i+1] = 0.0;
        for (int8_t j=0; j<num_antennes; j++) {
            a = Rinv[2*(j+i*num_antennes)];
            b = Rinv[2*(j+i*num_antennes)+1];
            c = a_theta_phi[2*j];
            d = a_theta_phi[2*j+1];
            buffer[2*i]   += a*c - b*d;
            buffer[2*i+1] += b*c + a*d;
        }
    }

    // Calculer a_theta_phi^H * Rinv * a_theta_phi
    for (int8_t i=0;i<num_antennes; i++) {
        a = a_theta_phi_H[2*i];
        b = a_theta_phi_H[2*i+1];
        c = buffer[2*i];
        d = buffer[2*i+1];

        normalisation_coeff_re += a*c - b*d;
        //normalisation_coeff_im += b*c + a*d;
    }

    *re = 1/normalisation_coeff_re;

    return;
}

void calculer_poids_optimaux(float* Rinv, float* a_theta_phi, int8_t num_antennes, float* w_opt) {
    float normalisation_coeff_re = 0;
    float normalisation_coeff_im = 0;
    float a_theta_phi_H[num_antennes*2];
    calculer_transconjugue(a_theta_phi, num_antennes, a_theta_phi_H);

    float a,b,c,d;

    float buffer[num_antennes*2];

    // Calculer Rinv * a_theta_phi
    for (int8_t i=0; i<num_antennes; i++) {
        buffer[2*i] = 0;
        buffer[2*i+1] = 0;
        for (int8_t j=0; j<num_antennes; j++) {
            a = Rinv[2*(j+i*num_antennes)];
            b = Rinv[2*(j+i*num_antennes)+1];
            c = a_theta_phi[2*j];
            d = a_theta_phi[2*j+1];
            buffer[2*i]   += a*c - b*d;
            buffer[2*i+1] += b*c + a*d;
        }
    }

    // Calculer a_theta_phi^H * Rinv * a_theta_phi
    for (int8_t i=0;i<num_antennes; i++) {
        a = a_theta_phi_H[2*i];
        b = a_theta_phi_H[2*i+1];
        c = buffer[2*i];
        d = buffer[2*i+1];

        normalisation_coeff_re += a*c - b*d;
        normalisation_coeff_im += b*c + a*d;
    }

    float norm_re = normalisation_coeff_re/(normalisation_coeff_re*normalisation_coeff_re + normalisation_coeff_im*normalisation_coeff_im);
    float norm_im = -normalisation_coeff_im/(normalisation_coeff_re*normalisation_coeff_re + normalisation_coeff_im*normalisation_coeff_im);

    // Calculer 1/(a_theta_phi^H * Rinv * a_theta_phi) * Rinv * a_theta_phi :
    a = norm_re;
    b = norm_im;

    for (int8_t i=0;i<num_antennes; i++) {
        c = buffer[2*i];
        d = buffer[2*i+1];

        w_opt[2*i] = a*c - b*d;
        w_opt[2*i+1] = b*c + a*d;
    }

    return;
}



/**
 * BLOC DE FONCTIONS PERMETTANT DE CALCULER Y
 */
void calculer_y(float* w_opt, int32_t* input, int8_t num_antennes, int8_t snapshot_index, float* y) {
    float w_opt_H[num_antennes*2];
    calculer_transconjugue(w_opt, num_antennes, w_opt_H);

    float a,b,c,d;

    // R�initialiser
    y[0] = 0.0f;
    y[1] = 0.0f;

    for (int8_t j=0; j<num_antennes; j++) {
        a = w_opt_H[2*j];
        b = w_opt_H[2*j+1];

        int index = 2*(j + snapshot_index * num_antennes);
        c = input[index];
        d = input[index+1];

        y[0] += a*c - b*d;
        y[1] += b*c + a*d;

    }
    return;
}

void print_list_int1(int* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%d", list[i]);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

void print_list_float1(float* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%e", list[i]);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

void print_list_double(double* list, int32_t size) {
    if (list == NULL || size <= 0) {
        printf("[]\n");
        return;
    }

    printf("size of int32_t : %d\n",sizeof(int32_t));
    printf("List size : %d\n", size);
    printf("[");

    for (int32_t i = 0; i < size; i++) {
        if (i > 0 && i % 10 == 0) {
            printf("\n ");
        }
        printf("%e", list[i]);
        if (i < size - 1) {
            printf(", ");
        }
    }
    printf("]\n");
}

int32_t caponBeamforming2D_process(CaponBeamforming2DHWA_Config *cfg, float *output){
    // Fonction pour faire nous m�me le capon beamforming !!!

    /**
     * cfg : CaponBeamforming2DHWA_Config qui stocke les param�tres, et les addresses des buffers � op�rer.
     *
     * output : matrice complexe (n_phi, n_theta, 2)
     *      premier axe : angles azimuth (phi)
     *      deuxi�me axe : angle elevation (theta)
     *      troisi�me axe : r�el/complexe
     */
    gStart_time = CycleCounterP_getCount32();

    int32_t* input = cfg->hwRes.caponBeamforming2DInputData;
    //print_list_int1(input, 32*6*2);

    /**
     * input : matrice (n_frames, n_antennes, 2)
     *      premier axe : frames diff�rentes,
     *      deuxi�me axe : antennes diff�rentes,
     *      troisi�me axe: r�el/imag
     */

    uint8_t     numVirtualAntennas = cfg->staticCfg.numVirtualAntennas;
    uint16_t    numSnapshots = cfg->staticCfg.numSnapshots;
    uint8_t     numAnglesToSampleAzimuth = cfg->staticCfg.numAnglesToSampleAzimuth; //phi
    uint8_t     numAnglesToSampleElevation = cfg->staticCfg.numAnglesToSampleElevation; //theta
    uint8_t*    antennaCoordinates = cfg->staticCfg.antennaCoordinates;

    float phi_offset=0.0; // X
    float theta_offset=30.0; // Y

    float phi_range = 180.0; // X
    float theta_range = 30.0; // Y

    float alpha=PI/180*(0+180);

    float epsilon = 0.10;

    float phi_min = PI/180*(-1*phi_range + phi_offset);
    float phi_max = PI/180*(1*phi_range + phi_offset);
    float theta_min = PI/180*(-1*theta_range + theta_offset);
    float theta_max = PI/180*(1*theta_range + theta_offset);

    int8_t spectre_capon =1;

    float theta;
    float phi;

    // Calculer la matrice de covariance
    float R[numVirtualAntennas * numVirtualAntennas*2];
    memset(R, 0, sizeof(float)*numVirtualAntennas * numVirtualAntennas*2);
    calculer_matrice_de_covariance(input, numVirtualAntennas, numSnapshots, R);

    gCalcul_matrice_covariance_t = CycleCounterP_getCount32()-gStart_time;

    int16_t sizeR = numVirtualAntennas*numVirtualAntennas*2;
    float maxR = R[0];
    for (int16_t k=0; k<sizeR; k++) {
        if (R[k] > maxR) {
            maxR = R[k];
        }
    }
    normalize(R, numVirtualAntennas, maxR);

    // Inverser la matrice de covariance
    float Rinv[numVirtualAntennas * numVirtualAntennas*2];
    int8_t retVal=0;
    retVal = inverser_matrice_de_covariance(R, numVirtualAntennas, Rinv, epsilon);
    if (retVal <0) {
        printf("Matrice de covariance non inversible, est-ce que les antennes ont ete bien parametrees ?\n");
        return -1;
    }
    gCalcul_inverse_matrice_cov_t = CycleCounterP_getCount32()-(gCalcul_matrice_covariance_t+gStart_time);

    uint8_t theta_index_max = numAnglesToSampleElevation;
    uint8_t phi_index_max = numAnglesToSampleAzimuth;

    float a_theta_phi[numVirtualAntennas*2];
    float w_opt[numVirtualAntennas*2];
    float y_theta_phi[2];
    float re;

    int bigindex=0;

    for (uint8_t phi_index=0; phi_index < phi_index_max; phi_index++){
        phi = phi_min + phi_index*(phi_max - phi_min)/(numAnglesToSampleAzimuth-1);

        for (uint8_t theta_index=0; theta_index < theta_index_max; theta_index++){
            theta = theta_min + theta_index*(theta_max - theta_min)/(numAnglesToSampleElevation-1);
            memset(y_theta_phi, 0, sizeof(y_theta_phi));

            // Calculer le steering vector
            calculer_steering_vector(theta, phi, alpha, numVirtualAntennas, antennaCoordinates, a_theta_phi);
            if (phi_index==0 && theta_index==0) {
                gCalcul_steering_vector_t = CycleCounterP_getCount32()-(gCalcul_inverse_matrice_cov_t+gCalcul_matrice_covariance_t+gStart_time);
            }


            if (spectre_capon==1) {
                //Calculer spectre capon
                calculer_spectre_capon(Rinv, a_theta_phi, numVirtualAntennas, &re);
                y_theta_phi[0] = re*maxR;
                y_theta_phi[1] = 0;
                if (phi_index==0 && theta_index==0) {
                    gCalcul_caponSpectrum_t = CycleCounterP_getCount32()-(gCalcul_steering_vector_t + gCalcul_inverse_matrice_cov_t+gCalcul_matrice_covariance_t+gStart_time);
                }
            } else {
                // Calculer Wopt
                calculer_poids_optimaux(Rinv, a_theta_phi, numVirtualAntennas, w_opt);

                // Calculer y(theta, phi)
                // Prendre le premier snapshot
                calculer_y(w_opt, input, numVirtualAntennas, 0, y_theta_phi);
            }

            // Associer y(theta, phi) � sa place dans output
            // output[phi, theta] = y_theta_phi
            //float intensite = y_theta_phi[0]*y_theta_phi[0] + y_theta_phi[1]*y_theta_phi[1];
            bigindex = theta_index + phi_index*numAnglesToSampleElevation;
            //printf("%f %f\n", y_theta_phi[0], y_theta_phi[1]);
            output[(bigindex)*2] = (float) y_theta_phi[0];
            output[(bigindex)*2+1] = (float) y_theta_phi[1];
        }
    }
    gCalcul_boucles_t = CycleCounterP_getCount32()-(gCalcul_inverse_matrice_cov_t+gCalcul_matrice_covariance_t+gStart_time);

    //print_list_float1(output,1024);
    gEndTime = CycleCounterP_getCount32()-gStart_time;

    return 0;
}
