import numpy as np
from sklearn.cluster import DBSCAN


class HeightEstimator:
    def __init__(
            self,
            epsilon= 0.08,
            k= 5,
            alpha=2,
            p= 0.999,       # desired confidence
            r=0.8,          # expected inlier ratio (conservative)
            delta= 0.05     # inlier distance threshold in meters
        ):
        self.epsilon = epsilon
        self.k = k
        self.alpha = alpha
        self.p = p
        self.r = r
        self.delta = delta
        return
    
    def process(self, all_points, verbose=False):
        
        all_points = np.array(all_points)
        # Remove points at or near origin (r < 0.05m)
        r = np.linalg.norm(all_points[:, :3], axis=1)
        all_points = all_points[r > 0.05]
        
        z_list = all_points[:, 2]
        z_list = self.filter_elevation_stacks(pc=all_points)
        z_list = self.remove_false_points(z_list)

        #result_dict = self.iqr_outlier_analysis(z_list, verbose=verbose)
        #clean_z = result_dict["clean_data"]
        
        # Level 1: z-slice using IQR output
        S1, floor_z_est = self.z_slice(S1=z_list, all_points=all_points)
        # Level 2: statistical outlier removal (KNN)
        S2 = self.knn_mean_distances(S1=S1)
        # Level 3: RANSAC plane fit
        S3 = self.RANSAC(S2=S2)
        # Final refit via PCA on all inliers
        a,b,c,d_final = self.PCA(S3)
        result_dict = {
            "floor_z_est":floor_z_est,
            "a":a,
            "b":b,
            "c":c,
            "d_final":d_final
        }
        return result_dict
    
    def iqr_outlier_analysis(self, data, verbose=False):
        data = np.array(data)
        Q1 = np.percentile(data, 25)
        Q3 = np.percentile(data, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outliers  = data[(data < lower_bound) | (data > upper_bound)]
        clean_data = data[(data >= lower_bound) & (data <= upper_bound)]
        if verbose:
            print(f"Q1            : {Q1:.3f}")
            print(f"Q3            : {Q3:.3f}")
            print(f"IQR           : {IQR:.3f}")
            print(f"Lower bound   : {lower_bound:.3f}")
            print(f"Upper bound   : {upper_bound:.3f}")
            print(f"Outliers      : {outliers}")
            print(f"# of outliers : {len(outliers)}")
        result_dict = {
            "clean_data":clean_data,
            "Q1":Q1,
            "Q3":Q3,
            "IQR":IQR,
            "Lower bound":lower_bound,
            "Upper bound":upper_bound,
            "Outliers":outliers,
            "# of outliers": len(outliers)
        }
        return result_dict

    def remove_false_points(self, data):
        z_max = -0.05
        z_min = -2.5
        clean_data = data[(data >= z_min) & (data <= z_max)]
        return clean_data

    def z_slice(self, S1, all_points):
        # The floor cluster is near the mode of clean_z
        hist, bin_edges = np.histogram(S1, bins=50)
        floor_z_est = (bin_edges[np.argmax(hist[:-1])] + bin_edges[np.argmax(hist[:-1]) + 1]) / 2
        print(f"\nEstimated floor z : {floor_z_est:.3f} m")

        self.epsilon = 0.08  # z-slice half-width in meters
        mask_slice = np.abs(all_points[:, 2] - floor_z_est) < self.epsilon
        S1 = all_points[mask_slice]
        print(f"Points after z-slice : {len(S1)}")
        return S1, floor_z_est

    def knn_mean_distances(self, S1):
        N = len(S1)
        mean_dists = np.zeros(N)
        for i in range(N):
            diffs = S1 - S1[i]                      # (N, 3)
            dists = np.sqrt((diffs ** 2).sum(axis=1))       # (N,)
            dists[i] = np.inf                               # exclude self
            nearest = np.sort(dists)[:self.k]
            mean_dists[i] = nearest.mean()

        mu_d    = mean_dists.mean()
        sigma_d = mean_dists.std()
        mask_sor = mean_dists < (mu_d + self.alpha * sigma_d)
        S2 = S1[mask_sor]
        print(f"Points after SOR     : {len(S2)}")
        return S2

    def RANSAC(self, S2):
        K_ransac = int(np.ceil(np.log(1 - self.p) / np.log(1 - self.r ** 3)))
        print(f"RANSAC iterations    : {K_ransac}")

        best_inliers = []
        rng = np.random.default_rng(42)

        for _ in range(K_ransac):
            # sample 3 random points
            idx = rng.choice(len(S2), 3, replace=False)
            S2 = S2[:, :3]
            q1, q2, q3 = S2[idx]

            # fit exact plane through 3 points
            v1 = q2 - q1
            v2 = q3 - q1
            n  = np.cross(v1, v2)
            norm = np.linalg.norm(n)
            if norm < 1e-9:
                continue                                        # degenerate sample
            n = n / norm
            d = -n @ q1

            # count inliers
            distances = np.abs(S2 @ n + d)
            inliers   = np.where(distances < self.delta)[0]

            if len(inliers) > len(best_inliers):
                best_inliers = inliers

        S3 = S2[best_inliers]
        print(f"Inliers after RANSAC : {len(S3)}")
        return S3
    
    def PCA(self, S3):
        S3 = S3[np.all(np.isfinite(S3), axis=1)]
        if len(S3) < 3:
            raise ValueError(f"Not enough valid points for PCA: {len(S3)} after cleaning")
        
        centroid = S3.mean(axis=0)
        centered = S3 - centroid
        C = (centered.T @ centered) / len(S3)
        C = C + 0.0001*np.eye(3)
        eigenvalues, eigenvectors = np.linalg.eigh(C)
        # smallest eigenvalue -> plane normal
        n_final = eigenvectors[:, np.argmin(eigenvalues)]
        d_final = -n_final @ centroid

        # ensure normal points upward (positive z component)
        if n_final[2] < 0:
            n_final = -n_final
            d_final = -d_final

        a, b, c = n_final
        return a,b,c, d_final

    def filter_elevation_stacks(self, pc: np.ndarray,
                                azimuth_tol_deg: float = 3.0,
                                range_tol: float = 0.5,
                                elev_tol_deg: float = 10.0,
                                min_stack_size: int = 3,
                                keep_bottom: int = 3) -> np.ndarray:
        """
        Detects points at same range & azimuth but stacked in elevation,
        keeps only the bottom `keep_bottom` (lowest z).

        Args:
            pc                : (N, 4+) array [x, y, z, doppler, ...]
            azimuth_tol_deg   : azimuth tolerance to consider "same column"
            range_tol         : range tolerance to consider "same column"
            elev_tol_deg      : elevation tolerance to consider points "close"
            min_stack_size    : min points in stack to trigger filtering
            keep_bottom       : how many lowest-z points to keep
        """
        if len(pc) == 0:
            return pc

        x, y, z = pc[:, 0], pc[:, 1], pc[:, 2]

        # --- Spherical coordinates ---
        r       = np.sqrt(x**2 + y**2 + z**2)          # 3D range
        azimuth = np.degrees(np.arctan2(x, y))          # azimuth angle
        elev    = np.degrees(np.arcsin(np.clip(z / r, -1, 1)))  # elevation angle

        # --- Cluster in (azimuth, range) space only ---
        # Points in the same "column" share azimuth + range
        features = np.column_stack([
            azimuth / azimuth_tol_deg,
            r       / range_tol,
        ])

        db = DBSCAN(eps=1.0, min_samples=2).fit(features)
        labels = db.labels_

        keep_mask = np.ones(len(pc), dtype=bool)

        for lbl in set(labels) - {-1}:
            cluster_idx = np.where(labels == lbl)[0]

            if len(cluster_idx) < min_stack_size:
                continue

            # Check that points are actually close in elevation
            elev_vals = elev[cluster_idx]
            elev_span = elev_vals.max() - elev_vals.min()
            if elev_span > elev_tol_deg * min_stack_size:
                continue  # spread too wide, probably not a reflection stack

            # Keep bottom `keep_bottom` by z
            z_vals     = z[cluster_idx]
            sorted_pos = cluster_idx[np.argsort(z_vals)]
            to_remove  = sorted_pos[keep_bottom:]

            keep_mask[to_remove] = False

        return pc[keep_mask]


