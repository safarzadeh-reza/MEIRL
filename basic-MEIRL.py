import numpy as np 
import matplotlib.pyplot as plt
import seaborn as sns

'''
A very simple dxd gridworld to test out multiple-experts IRL.
Agent can move in cardinal directions; moves in intended direction
with prob 90%, else uniform direction. If moves in illegal
direction, stays in place.

Will find optimal Q values by Q-learning.

Actions: 0 = up, 1 = right, 2 = down, 3 = left
'''

np.random.seed(1)

# Global params
D=8#6
MOVE_NOISE = 0.05
INTERCEPT_ETA = 10
INTERCEPT_REW = 1
WEIGHT = 2
M = 20 # number of actions used for importance sampling
N = 10 # number of trajectories per expert
Ti = 50 # length of trajectory
B = 100 # number of betas sampled for expectation
learn_rate = 0.0001

# Making gridworld
state_space = np.array([(i,j) for i in range(D) for j in range(D)])
action_space = list(range(4))
'''
rewards = np.ones((D,D))
rewards[0,0] = 5
rewards[D-1,D-1] = 5
rewards[0,D-1] = -5
rewards[D-1,0] = -5
'''
true_theta = np.array([4, 4, -6, -6, 0.1])
rewards = lin_rew_func(true_theta, state_space)
#sns.heatmap(rewards)

def manh_dist(p1, p2):
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def act_to_coord(a):
    d = {0: (-1, 0), 1: (0, 1), 2: (1, 0),
         3: (0,-1)}
    return d[a]

def state_index(tup):
    return D*tup[0] + tup[1]

def multi_state_index(states):
    return D*states[:,0]+states[:,1]

def transition(state_space, action_space):
    # 0 index = start state
    # 1 = action
    # 2 = next state
    S = len(state_space)
    A = len(action_space)
    TP = np.zeros((S, A, S))
    for s in range(S):
        x1 = state_space[s][0]
        y1 = state_space[s][1]
        for a in range(A):
            action = act_to_coord(a)
            for x2 in range(D):
                for y2 in range(D):
                    if ((x2 == x1 + action[0]) and
                        (y2 == y1 + action[1])):
                        TP[s,a,state_index((x2,y2))] += 1 - MOVE_NOISE
                    if manh_dist((x2, y2), state_space[s]) == 1:
                        TP[s,a,state_index((x2,y2))] += MOVE_NOISE/4
                    if ((x2, y2) == state_space[s]).all():
                        count = (x2 == 0 or x2 == D-1) + (y2 == 0 or y2 == D-1)
                        TP[s,a,state_index((x2,y2))] += count*MOVE_NOISE/4
                        if ((x1 + action[0] < 0) or
                            (x1 + action[0] >= D) or
                            (y1 + action[1] < 0) or
                            (y1 + action[1] >= D)):
                            TP[s,a,state_index((x2,y2))] += 1 - MOVE_NOISE
    return TP

TP = transition(state_space, action_space)

def grid_step(s, a):
    '''
    Given current state s and action a, returns resulting
    state.
    '''
    flip = np.random.rand()
    if flip < MOVE_NOISE:
        a = np.random.choice([0,1,2,3])
    new_state = s + act_to_coord(a)
    return np.minimum(np.maximum(new_state, 0), D-1)

def episode(s,T,policy,rewards,step_func,a=-1):
    '''
    Given any generic state, time horizon, policy, and
    reward structure indexed by the state, generates an
    episode starting from that state.

    step_func defines how a resulting state is generated
    from current state and action
    '''
    states = [s]
    if a < 0:
        a = np.random.choice(action_space, p=policy[tuple(s)])
    actions = [a]
    reward_list = [0]
    for _ in range(T-1):
        s = step_func(s,a)
        states.append(s)
        r = rewards[tuple(s)]
        reward_list.append(r)
        a = np.random.choice(action_space, p=policy[tuple(s)])
        actions.append(a)
    reward_list.append(rewards[tuple(s)])
    return np.array(states), actions, reward_list

def stoch_policy(det_policy, action_space):
    '''
    Turns an array of actions corresponding to a
    deterministic policy into a "stochastic" policy
    (1 on the action chosen, 0 else)
    '''
    x = np.repeat(range(D), D)
    y = np.tile(range(D), D)
    z = np.ravel(det_policy)
    out = np.zeros((D,D,len(action_space)))
    out[x,y,z] = 1
    return out

def visualize_policy(rewards, policy):
    '''
    Heatmap representing the input policy in the state
    space with the input rewards.
    '''
    pol = np.argmax(policy, axis=2)
    sns.heatmap(rewards)
    for x in range(D):
        for y in range(D):
            dx = (pol[x,y] % 2)*0.2*(2 - pol[x,y])
            dy = ((pol[x,y]-1) % 2)*0.2*(pol[x,y] - 1)
            plt.arrow(y+0.5,x+0.5,dx,dy,head_width=0.1,
                      color="black",alpha=0.9)

def eps_greedy(Q, eps, action_space):
    best = np.argmax(Q, axis=2)
    po = stoch_policy(best, action_space)
    po += eps/(len(action_space)-1)*(1 - po) - eps*po
    return po

def Qlearn(rate, gam, eps, K, T, state_space, action_space,
           rewards, policy, Q):
    '''
    Q-learning. Returns the corresponding optimal policy and Q*.
    '''
    for _ in range(K):
        st = state_space[np.random.choice(len(state_space))]
        for _ in range(T):
            policy = eps_greedy(Q, eps, action_space)
            at = np.random.choice(action_space, p=policy[tuple(st)])    
            sp = grid_step(st,at)
            rt = rewards[tuple(sp)]
            qnext = np.max(Q[sp[0],sp[1]])
            qnow = Q[st[0],st[1],at]
            Q[st[0],st[1],at] += rate*(rt + gam*qnext - qnow)
            st = sp
    policy *= 0
    for i in range(D):
        for j in range(D):
            policy[i,j,np.argmax(Q[i,j])] = 1
    return policy, Q

def eta(st):
    return np.array([abs(st[0]-1), abs(st[1]-1), abs(st[0]-(D-2)),
                     abs(st[1]-(D-2)), INTERCEPT_ETA])

def mu(s, alpha):
    return np.dot(eta(s), alpha)

def mu_all(alpha):
    muvals = np.zeros((D,D))
    for i in range(D):
        for j in range(D):
            muvals[i,j] = mu((i,j), alpha)
    return muvals

def softmax(v, beta, axis=False):
    if axis:
        x = beta[:,:,None]*v
        w = np.exp(x - np.max(x, axis=axis)[:,:,None])
        z = np.sum(w, axis=axis)
        return np.divide(w, z[:,:,None])
    else:
        w = np.exp(beta*v)
        z = np.sum(w)
        return w / z

def beta_func(alpha, sigsq):
    '''
    Computes beta for whole state space.
    '''
    noise = np.random.normal(loc=0,scale=np.sqrt(sigsq),
                             size=(D,D))
    muvals = mu_all(alpha)
    return muvals + noise

def locally_opt(Q_star, alpha, sigsq):
    '''
    Given optimal Q* and some "state of expertise",
    returns a stochastic policy for an agent whose
    beta is ideal centered around that state.

    high beta = high expertise

    CHANGE THIS
    '''
    beta = beta_func(alpha, sigsq)
    policy = softmax(Q_star, beta, 2)
    det_pol = np.argmax(policy, axis=2)
    return policy, det_pol


'''
Going to test on trajectories from Q* model rather than one-step,
will see how bad...
'''

# Misspecified reward bases?

# Alpha vectors for the centers of the grid world
# where each expert is closest to optimal.
alpha1 = np.array([-WEIGHT, -WEIGHT, 0, 0, 1]) # (1,1)
alpha2 = np.array([-WEIGHT, 0, 0, -WEIGHT, 1]) # (1,4)
alpha3 = np.array([0, -WEIGHT, -WEIGHT, 0, 1]) # (4,1)
alpha4 = np.array([0, 0, -WEIGHT, -WEIGHT, 1]) # (4,4)
p = alpha1.shape[0]
d = 5
m = 4

'''
sigsq1 = 25
sigsq2 = 25
sigsq3 = 25
sigsq4 = 25
'''

sigsq1 = 2
sigsq2 = 2
sigsq3 = 2
sigsq4 = 2

ex_alphas = np.stack([alpha1, alpha2, alpha3, alpha4])
ex_sigsqs = np.array([sigsq1, sigsq2, sigsq3, sigsq4])

np.random.seed(1)
init_det_policy = np.random.choice([0,1,2,3], size=(D,D))
init_policy = stoch_policy(init_det_policy, action_space)
init_Q = np.random.rand(D,D,4)
opt_policy, Q = Qlearn(0.5, 0.8, 0.1, 10000, 20, state_space,
          action_space, rewards, init_policy, init_Q)
          # This seems to converge robustly to optimal policy,
          # although Q values have some variance in states where
          # it doesn't really matter
visualize_policy(rewards, opt_policy)
#pol1 = locally_opt(Q, alpha1, sigsq1)[0]
#pol2 = locally_opt(Q, alpha2, sigsq2)[0]
#pol3 = locally_opt(Q, alpha3, sigsq3)[0]
#pol4 = locally_opt(Q, alpha4, sigsq4)[0]







###### Phase 2 ######

'''
CHANGED THE REWARD FUNC!

may want to randomly generate a bunch of these
'''

def arr_radial(s, c):
    #return np.exp(-5*((s[:,0]-c[0])**2+(s[:,1]-c[1])**2))
    return np.exp(-2*((s[:,0]-c[0])**2+(s[:,1]-c[1])**2))

def psi_all_states(state_space):
    # d x D**2
    '''
    return np.array([arr_radial(state_space, (0,0)),
                    arr_radial(state_space,(D-1,D-1)),
                    arr_radial(state_space, (0,D-1)),
                    arr_radial(state_space, (D-1,0)),
                     INTERCEPT_REW*np.ones(len(state_space))])
    '''
    return np.array([arr_radial(state_space, (0,2)),
                    arr_radial(state_space,(D-2,D-1)),
                    arr_radial(state_space, (3,D-2)),
                    arr_radial(state_space, (D-1,0)),
                     INTERCEPT_REW*np.ones(len(state_space))])

def lin_rew_func(theta, state_space):
    '''
    Using radial features above and theta below,
    gives a very close approximation to the true
    RF.
    '''
    return np.reshape(theta.dot(psi_all_states(state_space)), (D, D))
    
def arr_expect_reward(rewards, data, TP, state_space):
    '''
    data is m x 2 x Ti
    '''
    return TP[data[:,0], data[:,1]].dot(np.ravel(rewards)) #m x Ti

def grad_lin_rew(data, state_space):
    '''
    Input (data) is m x 2 x Ti

    Output should be m x d x Ti

    Each column is E(s'|st,at)(psi(s')) where psi is
    feature

    Looks correct!
    '''
    probs = TP[data[:,0], data[:,1]] # m x Ti x D**2
    return np.swapaxes(probs.dot(psi_all_states(state_space).transpose()), 1, 2)

def init_state_sample(state_space):
    '''
    Returns initial state index; uniform for simplicity
    '''
    return state_space[np.random.choice(len(state_space))]

def myo_policy(beta, s, TP, rewards):
    expect_rew = TP[state_index(s)].dot(np.ravel(rewards))
    return softmax(expect_rew, beta)

def synthetic_traj_myo(rewards, alpha, sigsq, i, Ti, state_space, action_space,
                       init_state_sample, TP):
    '''
    Generate a fake trajectory based on given
    policy. Need to separately generate
    variational distribution parameters if want to
    use those.
    
    EDIT FOR LOCALLY OPT
    '''
    s = init_state_sample(state_space)
    states = [s]
    beta = mu(s, alpha[i]) + np.random.normal(scale=np.sqrt(sigsq[i]))
    a = np.random.choice(action_space, p = myo_policy(beta, s,
               TP, rewards))
    actions = [a]
    for _ in range(Ti-1):
        s = grid_step(s,a)
        states.append(s)
        beta = mu(s, alpha[i]) + np.random.normal(scale=np.sqrt(sigsq[i]))
        a = np.random.choice(action_space, p = myo_policy(beta, s,
               TP, rewards))
        actions.append(a)
    return list(multi_state_index(np.array(states))), actions

def see_trajectory(reward_map, state_seq):
    '''
    Input state seq is in index form; can transform to tuples
    '''
    state_seq = [state_space[s] for s in state_seq]
    for s in state_seq:
        sns.heatmap(reward_map)
        plt.annotate('*', (s[1]+0.2,s[0]+0.7), color='b', size=24)
        plt.show()

def make_data(Q, alphas, sigsqs, reward_str, N, Ti):
    '''
    Creates N trajectories each for local experts, given Q,
    alphas, sigsqs, rewards (which may be "true" or
    based on current guesses!)
    
    OLD
    '''
    policies = [locally_opt(Q, alphas[i],
                            sigsqs[i])[0] for i in range(m)]
    trajectories = [
        [synthetic_traj(reward_str, policies[i], Ti, state_space,
                        action_space, init_state_sample)[:2] for i in range(m)]
        for _ in range(N)
    ]
    # first index is N
    # second is m
    return trajectories 

def make_data_myopic(alpha, sigsqs, reward_str, N, Ti, state_space, action_space,
                     init_state_sample, TP, m):
    '''
    Creates N trajectories each for local experts, given Q,
    alphas, sigsqs, rewards (which may be "true" or
    based on current guesses!)
    '''
    trajectories = [
        [synthetic_traj_myo(reward_str, alpha, sigsq, i, Ti, state_space, action_space,
                       init_state_sample, TP) for i in range(m)]
        for _ in range(N)
    ]
    # first index is N
    # second is m
    return trajectories 

def eta_mat(data):
    arr = np.array([abs(data[:,0,:] // D - 1),
                    abs(data[:,0,:] % D - 1),
                    abs(data[:,0,:] // D - (D-2)),
                    abs(data[:,0,:] % D - (D-2)),
                    INTERCEPT_ETA*np.ones(data[:,0,:].shape)])

    return np.swapaxes(arr, 0, 1)

def RE_all(theta, data, TP, state_space, m):
    reward_est = lin_rew_func(theta, state_space)
    R_all = arr_expect_reward(reward_est, data, TP, state_space) # m x Ti
    E_all = eta_mat(data)
    return R_all, E_all

def sample_all_MV_beta(phi, alpha, sigsq, theta, R_all, E_all, data, TP,
                       state_space, B, m):
    '''
    For each expert, get B samples of betas from variational posterior.
    Assumes the input data consists of one trajectory for each expert.

    Output is m x B x Ti
    '''
    mus = sigsq[:,None]*R_all + np.einsum('ijk,ij->ik', E_all, alpha) + phi[:,0][:,None]*np.ones(R_all.shape[:2])
    Covs = np.einsum('i,jk->ijk', sigsq+phi[:,1], np.eye(R_all.shape[1]))

    #mus = np.array([sigsq[i]*R_all[i] + E_all[i].transpose().dot(alpha[i]) + phi[i,0]*np.ones(R_all[i].shape[0]) for i in range(m)])
    #Covs = np.array([(sigsq[i]+phi[i,1])*np.eye(R_all[i].shape[0]) for i in range(m)])
    return np.array([np.random.multivariate_normal(mus[i], Covs[i], B) for i in range(m)])

'''
Need to average over sample betas in the
following four functions
'''

def rho(state_space):
    return 1/len(state_space)

def uniform_action_sample(action_space, M):
    return list(np.random.choice(action_space, M))

def imp_samp_data(data, impa, j, m, Ti):
    actions = impa[j]*np.ones((m,Ti))
    out = np.stack((data[:,0,:], actions))
    return np.swapaxes(out, 0, 1)

def traj_TP(data, TP, Ti, m):
    '''
    data = m x 2 x Ti
    output = m x (Ti-1)

    Computes TPs for (s1, a1) to s2, ..., st-1, at-1 to st
    '''
    s2_thru_sTi = TP[data[:,0,:(Ti-1)],data[:,1,:(Ti-1)]]
    return s2_thru_sTi[np.arange(m)[:,None], np.arange(Ti-1), data[:,0,1:]]


def SGD(phi, theta, alpha, sigsq, g_phi, g_theta, g_alpha, g_sigsq, learn_rate):
    phi = phi + learn_rate*g_phi
    phi[:,1] = np.maximum(phi[:,1], 0.01)
    theta = theta + learn_rate*g_theta
    alpha = alpha + learn_rate*g_alpha
    sigsq = np.maximum(sigsq + learn_rate*g_sigsq, 0.01)
    return phi, theta, alpha, sigsq

def y_t_SGD(phi, phi_m, theta, theta_m, alpha, alpha_m, sigsq, sigsq_m, t):
    return phi, theta, alpha, sigsq

def y_t_nest(phi, phi_m, theta, theta_m, alpha, alpha_m, sigsq, sigsq_m, t):
    const = (t-1)/(t+2)
    return (phi - const*(phi - phi_m),
            theta - const*(theta - theta_m),
            alpha - const*(alpha - alpha_m),
            sigsq - const*(sigsq - sigsq_m))

def AEVB(theta, alpha, sigsq, phi, traj_data, TP, state_space,
         action_space, B, m, M, Ti, learn_rate, reps, y_t, update, plot=True):
    '''
    Need the expert trajectories

    y_t is the function used to define modified iterate for Nesterov, if
    applicable
    
    update is e.g. SGD or Adam
    '''
    impa = uniform_action_sample(action_space, M)
    N = len(traj_data)
    elbo = []
    phi_m = np.zeros_like(phi)
    theta_m = np.zeros_like(theta)
    alpha_m = np.zeros_like(alpha)
    sigsq_m = np.zeros_like(sigsq)
    t = 1
    # while error > eps:
    for _ in range(reps):
        for n in range(N):
            y_phi, y_theta, y_alpha, y_sigsq = y_t(phi, phi_m, theta, theta_m,
              alpha, alpha_m, sigsq, sigsq_m, t)
            data = np.array(traj_data[n]) # m x 2 x Ti
            R_all, E_all = RE_all(y_theta, data, TP, state_space, m)
            normals = np.array([np.random.multivariate_normal(np.zeros(Ti),
              np.eye(Ti), B) for i in range(m)])
            meanvec, denom, gvec, gnorm = grad_terms_re(normals,
              y_phi, y_alpha, y_sigsq, y_theta, data, R_all, E_all, Ti, m)
            logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi = logZ_re(normals,
              meanvec, denom, impa, y_theta, data, M, TP, R_all, E_all, action_space)
          
            lp = logp_re(state_space, Ti, y_sigsq, gnorm, data, TP, m, normals, R_all,
              logZvec, meanvec).mean(axis=1).sum()
            lq = logq_re(Ti, denom, normals).mean(axis=1).sum()
            elbo.append(lp - lq)
            #print(lp - lq)
              
            g_phi = phi_grad_re(y_phi, m, Ti, normals, denom, y_sigsq, glogZ_phi)
            g_theta = theta_grad_re(glogZ_theta, data, state_space, R_all, E_all,
              y_sigsq, y_alpha)
            g_alpha = alpha_grad_re(glogZ_alpha, E_all, R_all)
            g_sigsq = sigsq_grad_re(glogZ_sigsq, normals, Ti, y_sigsq, gnorm, denom,
              R_all, gvec)
          
            phi_m, theta_m, alpha_m, sigsq_m = phi, theta, alpha, sigsq
            phi, theta, alpha, sigsq = update(y_phi, y_theta, y_alpha, y_sigsq, g_phi,
              g_theta, g_alpha, g_sigsq, learn_rate)
            
            learn_rate *= 0.99
            t += 1
    if plot:
        plt.plot(elbo)
    return phi, theta, alpha, sigsq

def grad_terms_re(normals, phi, alpha, sigsq, theta, data, R_all,
             E_all, Ti, m):
    '''
    Computes quantities used in multiple computations of gradients.
    '''
    denom = sigsq + phi[:,1]
    sc_normals = (denom**(1/2))[:,None,None]*normals
    aE = np.einsum('ij,ijk->ik', alpha, E_all)
    meanvec = sc_normals + (sigsq[:,None]*R_all + aE + phi[:,0][:,None]*np.ones((m,Ti)))[:,None,:] #looks good
    gvec = sc_normals + (sigsq[:,None]*R_all + phi[:,0][:,None]*np.ones((m,Ti)))[:,None,:] #betas - aE[:,None,:]
    gnorm = np.einsum('ijk,ijk->ij', gvec, gvec)
    return meanvec, denom, gvec, gnorm

def logp_re(state_space, Ti, sigsq, gnorm, data, TP, m, normals, R_all, logZvec, meanvec):
    p1 = np.log(rho(state_space)) - Ti/2*np.log(2*np.pi*sigsq)[:,None] - 1/(2*sigsq)[:,None]*gnorm
    logT = np.log(traj_TP(data, TP, Ti, m))
    p2 = np.einsum('ijk,ik->ij', meanvec, R_all) - logZvec + np.sum(logT, axis=1)[:,None]
    return p1 + p2

def logq_re(Ti, denom, normals):
    epsnorm = np.einsum('ijk,ijk->ij', normals, normals)
    return -Ti/2*np.log(2*np.pi*denom)[:,None] - epsnorm/2

def phi_grad_re(phi, m, Ti, normals, denom, sigsq, glogZ_phi):
    '''
    Output is m x 2; expectation is applied

    WORKS, but slightly high variance
    
    Feasible?
    '''
    x = (phi[:,0][:,None]*np.ones((m,Ti)))[:,None,:] + (denom**(1/2))[:,None,None]*normals
    y1 = 1/sigsq[:,None]*x.sum(axis=2)
    y2 = np.einsum('ijk,ijk->ij', normals, x)/((2*sigsq*denom**(1/2))[:,None]) - Ti/(2*denom)[:,None]
    result = -glogZ_phi - np.stack((y1, y2))
    return np.swapaxes(np.mean(result, axis=2), 0, 1)

def alpha_grad_re(glogZ_alpha, E_all, R_all):
    '''
    WORKS!
    '''
    result = -glogZ_alpha + np.einsum('ijk,ik->ij', E_all, R_all)[:,None,:]
    return np.mean(result, axis=1)

def sigsq_grad_re(glogZ_sigsq, normals, Ti, sigsq, gnorm, denom, R_all,
                  gvec):
    '''
    WORKS!

    Feasible?
    '''
    q_grad = -Ti/(2*denom)
    x = -Ti/(2*sigsq) + np.einsum('ij,ij->i', R_all, R_all)
    y = np.einsum('ijk,ik->ij', normals, R_all)/(2*denom**(1/2))[:,None]
    z1 = R_all[:,None,:] + normals/(2*denom**(1/2))[:,None,None]
    z = 1/(sigsq[:,None])*np.einsum('ijk,ijk->ij', z1, gvec)
    w = 1/(2*sigsq**2)[:,None]*gnorm
    result = -glogZ_sigsq + x[:,None] + y - z + w - q_grad[:,None]
    return np.mean(result, axis=1)

def log_mean_exp(tensor):
    K = np.max(tensor, axis=2)
    expo = np.exp(tensor - K[:,:,None,:]) #getting ZEROS and INFs
    # USE LOG SUM EXP TRICK
    # may need K to be m x B x Ti; same shape as lvec
    return np.log(np.mean(expo,axis=2)) + K

def logZ_re(normals, meanvec, denom, impa, theta, data, M, TP,
            R_all, E_all, action_space):
    reward_est = lin_rew_func(theta, state_space)
    R_Z = np.swapaxes(np.array([arr_expect_reward(reward_est,
                      imp_samp_data(data, impa, j, m, Ti).astype(int),
                      TP, state_space) for j in range(M)]), 0, 1)
    lst = []
    for j in range(M):
        newdata = imp_samp_data(data, impa, j, m, Ti).astype(int)
        feat_expect = grad_lin_rew(newdata, state_space)
        lst.append(feat_expect)
    gradR_Z = np.swapaxes(np.array(lst), 0, 1)

    volA = len(action_space) # m x N x Ti 
    bterm = np.einsum('ijk,ilk->ijlk', meanvec, R_Z)
    expo = np.exp(bterm) #getting ZEROS and INFs
    lvec = np.log(volA) + log_mean_exp(bterm)#+ np.log(np.mean(expo,axis=2)) + K
    logZvec = lvec.sum(axis=2)

    gradR = grad_lin_rew(data, state_space)
    num1 = sigsq[:,None,None,None]*np.einsum('ijk,ilk->ijlk', R_Z, gradR)
    num2 = np.einsum('ijk,ilmk->ijlmk', meanvec, gradR_Z)
    expo = np.exp(bterm - np.max(bterm, axis=2)[:,:,None,:])
    num = expo[:,:,:,None,:]*(num1[:,None,:,:,:]+num2)
    numsum = num.sum(axis=2)
    den = expo.sum(axis=2)
    glogZ_theta = (numsum/den[:,:,None,:]).sum(axis=3)


    num_a = expo[:,:,:,None,:]*np.einsum('ijk,ilk->ijlk', R_Z, E_all)[:,None,:,:,:]
    numsum_a = num_a.sum(axis=2)
    glogZ_alpha = (numsum_a/den[:,:,None,:]).sum(axis=3)

    num_s = expo*np.einsum('ijk,ilk->iljk', R_Z, R_all[:,None,:] + normals/((2*denom**2)[:,None,None]))
    numsum_s = num_s.sum(axis=2)
    glogZ_sigsq = (numsum_s/den).sum(axis=2)

    num_p1 = expo*R_Z[:,None,:,:]
    num_p2 = expo*np.einsum('ijk,ilk->iljk', R_Z, normals/((2*denom**2)[:,None,None]))
    numsum_p1 = num_p1.sum(axis=2)
    numsum_p2 = num_p2.sum(axis=2)
    glogZ_phi = np.array([(numsum_p1/den).sum(axis=2), (numsum_p2/den).sum(axis=2)])
    return logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi

def theta_grad_re(glogZ_theta, data, state_space, R_all, E_all, sigsq, alpha):
    '''
    Output m x d

    WORKS!!!
    '''
    gradR = grad_lin_rew(data, state_space)
    X = sigsq[:,None]*R_all + np.einsum('ij,ijk->ik', alpha, E_all)
    result = -glogZ_theta + np.einsum('ijk,ik->ij', gradR, X)[:,None,:]
    return np.sum(np.mean(result, axis=1), axis=0)

'''
TO DO:
* make function that runs episodes with policy and
  collects rewards
* make function that trains a Q-learner on rewards
  defined by a given theta and compare reward
  gained by inferred theta vs true
'''

def total_reward(reps, policy, T, state_space, rewards):
    reward_list = []
    for _ in range(reps):
        s = state_space[np.random.choice(len(state_space))]
        ret = np.sum(episode(s,T,policy,rewards,grid_step)[2]) #true reward
        reward_list.append(ret)
    return reward_list

def cumulative_reward(reps, policy, T, state_space, rewards):
    reward_list = []
    for _ in range(reps):
        s = state_space[np.random.choice(len(state_space))]
        ret = episode(s,T,policy,rewards,grid_step)[2] #true reward
        reward_list.extend(ret)
    return reward_list

def evaluate(reps, policy, T, state_space, rewards, theta_est, init_policy,
             init_Q):
    reward_est = lin_rew_func(theta_est, state_space)
    est_policy = Qlearn(0.5, 0.8, 0.1, 10000, 20, state_space,
          action_space, reward_est, init_policy, init_Q)[0]
    true_rew = cumulative_reward(reps, policy, T, state_space, rewards)
    est_rew = cumulative_reward(reps, est_policy, T, state_space, rewards)
    plt.plot(np.cumsum(true_rew), color='b')
    plt.plot(np.cumsum(est_rew), color='r')
    
def rep_evaluate(reps, policy, T, state_space, rewards, init_policy,
             init_Q, J):
    true_rew = cumulative_reward(reps, policy, T, state_space, rewards)
    plt.plot(np.cumsum(true_rew), color='b') 
    for _ in range(J):
        theta_star = AEVB(theta, alpha, sigsq, phi, traj_data, TP, state_space,
         action_space, B, m, M, Ti, learn_rate, 20, y_t_nest, SGD, plot=False)[1]
        reward_est = lin_rew_func(theta_star, state_space)
        est_policy = Qlearn(0.5, 0.8, 0.1, 10000, 20, state_space,
          action_space, reward_est, init_policy, init_Q)[0]
        est_rew = cumulative_reward(reps, est_policy, T, state_space, rewards)
        plt.plot(np.cumsum(est_rew), color='r')
        
def evaluate_vs_random(reps, policy, T, state_space, rewards, init_policy,
             init_Q, J):
    true_rew = cumulative_reward(reps, policy, T, state_space, rewards)
    plt.plot(np.cumsum(true_rew), color='b') 
    for _ in range(J):
        theta_star = AEVB(theta, alpha, sigsq, phi, traj_data, TP, state_space,
         action_space, B, m, M, Ti, learn_rate, 20, y_t_nest, SGD, plot=False)[1]
        reward_est = lin_rew_func(theta_star, state_space)
        est_policy = Qlearn(0.5, 0.8, 0.1, 10000, 20, state_space,
          action_space, reward_est, init_policy, init_Q)[0]
        est_rew = cumulative_reward(reps, est_policy, T, state_space, rewards)
        plt.plot(np.cumsum(est_rew), color='r')
        
        reward_est = lin_rew_func(np.random.normal(size=d), state_space)
        est_policy = Qlearn(0.5, 0.8, 0.1, 10000, 20, state_space,
          action_space, reward_est, init_policy, init_Q)[0]
        est_rew = cumulative_reward(reps, est_policy, T, state_space, rewards)
        plt.plot(np.cumsum(est_rew), color='g')
    
# Initializations
np.random.seed(1)
    
phi = np.random.rand(m,2)
alpha = np.random.normal(size=(m,p))
sigsq = np.random.rand(m)
#theta = np.random.normal(size=d)
theta = np.array([0, 0, 0, 0, 0]) #prob a good baseline, complete ignorance of
# rewards

traj_data = make_data_myopic(ex_alphas, ex_sigsqs, rewards, N, Ti, state_space, action_space,
                     init_state_sample, TP, m)
data = np.array(traj_data[0]) # for testing
# first index is n=1 to N
# second index is expert
# third is states, actions

M = 20 # number of actions used for importance sampling
N = 20 # number of trajectories per expert
B = 100 # number of betas sampled for expectation

phi_star, theta_star, alpha_star, sigsq_star = AEVB(theta, alpha, sigsq, phi, traj_data, TP, state_space,
         action_space, B, m, M, Ti, learn_rate, 20, y_t_nest, SGD)
# this works p well, when true sigsq is set to 2 and the trajectories come
# from the truly specified model
phi_star_2, theta_star_2, alpha_star_2, sigsq_star_2 = AEVB(theta, alpha, sigsq, phi, traj_data, TP, state_space,
         action_space, B, m, M, Ti, learn_rate, 50, y_t_nest, SGD)

evaluate(10, opt_policy, 50, state_space, rewards, theta, init_policy,
             init_Q)

evaluate(10, opt_policy, 50, state_space, rewards, theta_star, init_policy,
             init_Q)

#true_theta = np.array([4, 4, -6, -6, 0.1])
#sns.heatmap(lin_rew_func(true_theta, state_space))

# Maybe massive sigma (used to be 25!) was just drowning out the signal...













##### gradient checking and old bad gradients #####

















def logZ(betas, impa, theta, data, M, TP, action_space):
    '''
    Importance sampling approximation of logZ
    and grad logZ
    '''
    reward_est = lin_rew_func(theta, state_space)

    R_Z = np.swapaxes(np.array([arr_expect_reward(reward_est,
                      imp_samp_data(data, impa, j, m, Ti).astype(int),
                      TP, state_space) for j in range(M)]), 0, 1)
    lst = []
    for j in range(M):
        newdata = imp_samp_data(data, impa, j, m, Ti).astype(int)
        feat_expect = grad_lin_rew(newdata, state_space)
        #probs = TP[newdata[:,0], newdata[:,1]] 
        lst.append(feat_expect)
    gradR_Z = np.swapaxes(np.array(lst), 0, 1)
    
    expo = np.exp(np.einsum('ijk,ilk->ijlk', betas, R_Z))
    volA = len(action_space) # m x N x Ti
    lvec = np.log(volA*np.mean(expo,axis=2)) # for all times
    logZvec = lvec.sum(axis=2)

    num = expo[:,:,:,None,:]*np.einsum('ijk,ilmk->ijlmk', betas, gradR_Z)
    numsum = num.sum(axis=2)
    den = expo.sum(axis=2)
    glogZ = (numsum/den[:,:,None,:]).sum(axis=3)
    # This appears to approximate the true logZ for the
    # grid world with 4 actions very well!
    return logZvec, glogZ # m x N; Not averaged over beta!

def grad_check_phi_re(phi, alpha, sigsq, theta, data, Ti,
                     m, state_space, B, impa, ix):
    '''
    Good on phi1, not on phi2
    '''
    epsilon = 1e-4

    R_all, E_all = RE_all(theta, data, TP, state_space, m)
    normals = np.array([np.random.multivariate_normal(np.zeros(Ti),
      np.eye(Ti), B) for i in range(m)])
    meanvec, denom, gvec, gnorm = grad_terms_re(normals,
      phi, alpha, sigsq, theta, data, R_all, E_all, Ti, m)
    logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi = logZ_re(normals, meanvec, denom, impa, theta, data, M, TP, R_all, E_all,
                    action_space)
    a_p_g = phi_grad_re(phi, m, Ti, normals, denom, sigsq, glogZ_phi)

    left = phi.copy()
    left[:,ix] += epsilon
    right = phi.copy()
    right[:,ix] -= epsilon
    meanvec_l, denom_l, gvec_l, gnorm_l = grad_terms_re(normals,
      left, alpha, sigsq, theta, data, R_all, E_all, Ti, m)
    meanvec_r, denom_r, gvec_r, gnorm_r = grad_terms_re(normals,
      right, alpha, sigsq, theta, data, R_all, E_all, Ti, m)
    logZvec_l, glogZ_theta_l, glogZ_alpha_l, glogZ_sigsq_l, glogZ_phi_l = logZ_re(normals,
      meanvec_l, denom_l, impa, theta, data, M, TP, R_all, E_all, action_space)
    logZvec_r, glogZ_theta_r, glogZ_alpha_r, glogZ_sigsq_r, glogZ_phi_r = logZ_re(normals,
      meanvec_r, denom_r, impa, theta, data, M, TP, R_all, E_all, action_space)

    lp_l = logp_re(state_space, Ti, sigsq, gnorm_l, data, TP, m, normals, R_all,
      logZvec_l, meanvec_l)
    lp_r = logp_re(state_space, Ti, sigsq, gnorm_r, data, TP, m, normals, R_all,
      logZvec_r, meanvec_r)
    
    lq_l = logq_re(Ti, denom_l, normals)
    lq_r = logq_re(Ti, denom_r, normals)

    n_t_g = (lp_l - lq_l - lp_r + lq_r)/(2*epsilon)
    change = n_t_g.mean(axis=1)
    return a_p_g[:,ix], change

def grad_check_alpha_re(phi, alpha, sigsq, theta, data, Ti,
                     m, state_space, B, impa, ix):
    '''
    WORKS!
    '''
    epsilon = 1e-4

    R_all, E_all = RE_all(theta, data, TP, state_space, m)
    normals = np.array([np.random.multivariate_normal(np.zeros(Ti), np.eye(Ti), B) for i in range(m)])
    meanvec, denom, gvec, gnorm = grad_terms_re(normals,
      phi, alpha, sigsq, theta, data, R_all, E_all, Ti, m)

    logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi = logZ_re(normals, meanvec, denom, impa, theta, data, M, TP, R_all, E_all,
                    action_space)
    a_a_g = alpha_grad_re(glogZ_alpha, E_all, R_all)

    left = alpha.copy()
    left[:,ix] += epsilon
    right = alpha.copy()
    right[:,ix] -= epsilon
    meanvec_l, denom_l, gvec_l, gnorm_l = grad_terms_re(normals,
      phi, left, sigsq, theta, data, R_all, E_all, Ti, m)
    meanvec_r, denom_r, gvec_r, gnorm_r = grad_terms_re(normals,
      phi, right, sigsq, theta, data, R_all, E_all, Ti, m)
    logZvec_l, glogZ_theta_l, glogZ_alpha_l, glogZ_sigsq_l, glogZ_phi_l = logZ_re(normals,
      meanvec_l, denom_l, impa, theta, data, M, TP, R_all, E_all, action_space)
    logZvec_r, glogZ_theta_r, glogZ_alpha_r, glogZ_sigsq_r, glogZ_phi_r = logZ_re(normals,
      meanvec_r, denom_r, impa, theta, data, M, TP, R_all, E_all, action_space)

    lp_l = logp_re(state_space, Ti, sigsq, gnorm_l, data, TP, m, normals, R_all,
      logZvec_l, meanvec_l)
    lp_r = logp_re(state_space, Ti, sigsq, gnorm_r, data, TP, m, normals, R_all,
      logZvec_r, meanvec_r)
    
    lq_l = logq_re(Ti, denom, normals)
    lq_r = lq_l

    n_t_g = (lp_l - lq_l - lp_r + lq_r)/(2*epsilon)
    change = n_t_g.mean(axis=1)
    return a_a_g[:,ix], change

def grad_check_sigsq_re(phi, alpha, sigsq, theta, data, Ti,
                     m, state_space, B, impa, ix):
    '''
    Some variance still, but pretty good.
    '''
    epsilon = 1e-4

    R_all, E_all = RE_all(theta, data, TP, state_space, m)
    normals = np.array([np.random.multivariate_normal(np.zeros(Ti),
      np.eye(Ti), B) for i in range(m)])
    meanvec, denom, gvec, gnorm = grad_terms_re(normals,
      phi, alpha, sigsq, theta, data, R_all, E_all, Ti, m)
    logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi = logZ_re(normals, meanvec, denom, impa, theta, data, M, TP,
                    R_all, E_all, action_space)
    a_s_g = sigsq_grad_re(glogZ_sigsq, normals, Ti, sigsq, gnorm, denom, R_all,
                  gvec)

    left = sigsq.copy()
    left += epsilon
    right = sigsq.copy()
    right -= epsilon
    meanvec_l, denom_l, gvec_l, gnorm_l = grad_terms_re(normals,
      phi, alpha, left, theta, data, R_all, E_all, Ti, m)
    meanvec_r, denom_r, gvec_r, gnorm_r = grad_terms_re(normals,
      phi, alpha, right, theta, data, R_all, E_all, Ti, m)
    logZvec_l, glogZ_theta_l, glogZ_alpha_l, glogZ_sigsq_l, glogZ_phi_l = logZ_re(normals,
      meanvec_l, denom_l, impa, theta, data, M, TP, R_all, E_all, action_space)
    logZvec_r, glogZ_theta_r, glogZ_alpha_r, glogZ_sigsq_r, glogZ_phi_r = logZ_re(normals,
      meanvec_r, denom_r, impa, theta, data, M, TP, R_all, E_all, action_space)

    lp_l = logp_re(state_space, Ti, left, gnorm_l, data, TP, m, normals, R_all,
      logZvec_l, meanvec_l)
    lp_r = logp_re(state_space, Ti, right, gnorm_r, data, TP, m, normals, R_all,
      logZvec_r, meanvec_r)
    
    lq_l = logq_re(Ti, denom_l, normals)
    lq_r = logq_re(Ti, denom_r, normals)

    n_t_g = (lp_l - lq_l - lp_r + lq_r)/(2*epsilon)
    change = n_t_g.mean(axis=1)
    return a_s_g, change

def grad_check_theta_re(phi, alpha, sigsq, theta, data, Ti,
                     m, state_space, B, impa, ix):
    '''
    Much less variance! but still biased...

    Deduced that the bias is in the grad log.
    logZ itself is approximated, so as long as
    consistent this should still work...?
    '''
    epsilon = 1e-4

    R_all, E_all = RE_all(theta, data, TP, state_space, m)
    normals = np.array([np.random.multivariate_normal(np.zeros(Ti), np.eye(Ti), B) for i in range(m)])
    meanvec, denom, gvec, gnorm = grad_terms_re(normals,
      phi, alpha, sigsq, theta, data, R_all, E_all, Ti, m)

    logZvec, glogZ_theta, glogZ_alpha, glogZ_sigsq, glogZ_phi = logZ_re(normals, meanvec, denom, impa, theta, data, M, TP, R_all, E_all,
                    action_space)
    a_t_g = theta_grad_re(glogZ_theta, data, state_space, R_all, E_all, sigsq, alpha)


    left = theta.copy()
    left[ix] += epsilon
    right = theta.copy()
    right[ix] -= epsilon
    R_all_l, E_all_l = RE_all(left, data, TP, state_space, m)
    R_all_r, E_all_r = RE_all(right, data, TP, state_space, m)
    meanvec_l, denom_l, gvec_l, gnorm_l = grad_terms_re(normals,
      phi, alpha, sigsq, left, data, R_all_l, E_all_l, Ti, m)
    meanvec_r, denom_r, gvec_r, gnorm_r = grad_terms_re(normals,
      phi, alpha, sigsq, right, data, R_all_r, E_all_r, Ti, m)
    logZvec_l, glogZ_theta_l, glogZ_alpha_l, glogZ_sigsq_l, glogZ_phi_l = logZ_re(normals,
      meanvec_l, denom_l, impa, left, data, M, TP, R_all_l, E_all_l, action_space)
    logZvec_r, glogZ_theta_r, glogZ_alpha_r, glogZ_sigsq_r, glogZ_phi_r = logZ_re(normals,
      meanvec_r, denom_r, impa, right, data, M, TP, R_all_r, E_all_r, action_space)

    lp_l = logp_re(state_space, Ti, sigsq, gnorm_l, data, TP, m, normals, R_all_l,
      logZvec_l, meanvec_l)
    lp_r = logp_re(state_space, Ti, sigsq, gnorm_r, data, TP, m, normals, R_all_r,
      logZvec_r, meanvec_r)
    
    lq_l = logq_re(Ti, denom, normals)
    lq_r = lq_l

    n_t_g = (lp_l - lq_l - lp_r + lq_r)/(2*epsilon)
    change = (n_t_g.mean(axis=1)).sum()
    return a_t_g[ix], change


def grad_terms(betas, phi, alpha, sigsq, theta, data, R_all,
             E_all, Ti, logZvec, m):
    '''
    Computes quantities used in multiple computations of gradients.
    '''
    one = np.ones(Ti)
    aE = np.einsum('ij,ijk->ik', alpha, E_all)
    vec = betas - (sigsq[:,None]*R_all + aE + phi[:,0][:,None]*np.ones((m,Ti)))[:,None,:]
    denom = sigsq + phi[:,1]
    vecnorm = np.einsum('ijk,ijk->ij', vec, vec)  
    gvec = betas - aE[:,None,:]
    gnorm = np.einsum('ijk,ijk->ij', gvec, gvec)
    return one, vec, denom, vecnorm, gvec, gnorm

def logp(state_space, Ti, sigsq, gnorm, data, TP, m, betas, R_all, logZvec):
    p1 = np.log(rho(state_space)) - Ti/2*np.log(2*np.pi*sigsq)[:,None] - 1/(2*sigsq)[:,None]*gnorm
    logT = np.log(traj_TP(data, TP, Ti, m))
    p2 = np.einsum('ijk,ik->ij', betas, R_all) - logZvec + np.sum(logT, axis=1)[:,None]
    return p1 + p2

def logq(Ti, denom, vecnorm):
    return -Ti/2*np.log(2*np.pi*denom)[:,None] - vecnorm/((2*denom)[:,None])

def phi_grad(vec, one, denom, vecnorm, lp, lq):
    '''
    Output is m x 2; expectation is applied

    Will need to make sure feasible
    '''
    num1 = vec.dot(one)
    phigrad1 = num1/denom[:,None]
    phigrad2 = -Ti/(2*denom)[:,None] + vecnorm/((2*denom**2)[:,None])
    logdens = lp - lq
    return np.array([(phigrad1 * logdens).mean(axis=1), (phigrad2 * logdens).mean(axis=1)]).transpose()

def alpha_grad(E_all, gvec, vec, denom, lp, lq):
    '''
    Output m x p
    '''
    p1 = 1/sigsq[:,None,None]*np.einsum('ijk,ilk->ilj', E_all, gvec)
    p2 = 1/denom[:,None,None]*np.einsum('ijk,ilk->ilj', E_all, vec)
    return np.mean(p1 + p2*(lp - lq)[:,:,None], axis=1)

def sigsq_grad(Ti, sigsq, gnorm, denom, R_all, vec, lp, lq, vecnorm):
    '''
    Output m x 1

    Feasible!
    '''
    p1 = -Ti/(2*sigsq[:,None]) + gnorm/(2*sigsq[:,None]**2)
    p2 = -Ti/(2*denom[:,None]) + np.einsum('ik,ilk->il', R_all, vec)/denom[:,None] + vecnorm/(2*denom[:,None]**2)
    return np.mean(p1 + p2*(lp - lq), axis=1)

def theta_grad(data, betas, sigsq, state_space, denom, vec, glogZ, lp, lq):
    '''
    Output m x d
    '''
    gradR = grad_lin_rew(data, state_space) # m x d x Ti 
    p1 = -glogZ + np.einsum('ijk,imk->imj', gradR, betas) # each term is quite large
      #for theta index 0 and 4; however index 4 cancels entirely because psi is
      #constant!
    p2 = np.swapaxes((sigsq/denom)[:,None,None] * np.einsum('ijk,ilk->ijl', gradR, vec), 1, 2)
    return np.sum(np.mean(p1 + p2*(lp - lq)[:,:,None], axis=1), axis=0)